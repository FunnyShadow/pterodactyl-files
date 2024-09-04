import os
import yaml
import docker
import tempfile
import shutil
import argparse
import signal
import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TaskID
from rich.table import Table

class GracefulKiller:
    kill_now = False
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True

class DockerImageBuilder:
    REGISTRY_PRESETS = {
        'dockerhub': '',
        'ghcr': 'ghcr.io',
        'acr': 'azurecr.io',
        'ecr': 'amazonaws.com',
        'gcr': 'gcr.io',
    }

    def __init__(self, dockerfile_path='Dockerfile', config_path='config.yaml'):
        self.dockerfile_path = dockerfile_path
        self.config_path = config_path
        self.client = docker.from_env()
        self.config = self.load_config()
        self.default_resources_path = self.config.get('default_resources_path', 'resources')
        self.region = self.config.get('region', 'global')
        self.upload_config = self.config.get('upload', {})
        self.killer = GracefulKiller()
        self.console = Console()

    def load_config(self):
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def prepare_build_context(self, build_config):
        temp_dir = tempfile.mkdtemp()
        shutil.copy2(self.dockerfile_path, temp_dir)
        
        resources_path = build_config.get('resources_path', self.default_resources_path)
        if os.path.exists(resources_path):
            shutil.copytree(resources_path, os.path.join(temp_dir, 'resources'))
        return temp_dir

    def parse_progress(self, line):
        progress_pattern = r'(\d+(?:\.\d+)?[KMG]?B?)/(\d+(?:\.\d+)?[KMG]?B?)'
        match = re.search(progress_pattern, line)
        if match:
            current, total = match.groups()
            return self.convert_size_to_bytes(current), self.convert_size_to_bytes(total)
        return None, None

    def convert_size_to_bytes(self, size_str):
        units = {'K': 1024, 'M': 1024**2, 'G': 1024**3}
        if size_str[-1] in units:
            return int(float(size_str[:-1]) * units[size_str[-1]])
        elif size_str.endswith('B'):
            return int(float(size_str[:-1]))
        else:
            return int(float(size_str))

    def build_image(self, build_config):
        context_path = self.prepare_build_context(build_config)
        try:
            build_args = build_config.get('build_args', {})
            build_args['REGION'] = build_config.get('region', self.region)

            for line in self.client.api.build(
                path=context_path,
                dockerfile=os.path.basename(self.dockerfile_path),
                tag=build_config['tag'],
                buildargs=build_args,
                rm=True,
                decode=True
            ):
                if 'stream' in line:
                    yield 'stream', line['stream'].strip()
                elif 'status' in line:
                    yield 'status', line['status']
                    if 'progress' in line:
                        yield 'progress', line['progress']
                elif 'error' in line:
                    raise Exception(line['error'])

            image = self.client.images.get(build_config['tag'])
            return image
        finally:
            shutil.rmtree(context_path)

    def build_and_upload(self, build_config, progress):
        task_id = progress.add_task(f"[cyan]Building {build_config['tag']}", total=100)
        layer_tasks = {}
        
        try:
            for output_type, output in self.build_image(build_config):
                if self.killer.kill_now:
                    return None

                if output_type == 'stream':
                    progress.update(task_id, description=f"[cyan]Building {build_config['tag']}: {output}")
                elif output_type == 'status':
                    if 'Pulling from' in output:
                        layer_id = output.split()[-1]
                        layer_tasks[layer_id] = progress.add_task(f"[magenta]Pulling {layer_id}", total=100)
                    elif 'Pull complete' in output:
                        layer_id = output.split()[0]
                        if layer_id in layer_tasks:
                            progress.update(layer_tasks[layer_id], completed=100)
                elif output_type == 'progress':
                    layer_id = output.split()[0]
                    if layer_id in layer_tasks:
                        current, total = self.parse_progress(output)
                        if current is not None and total is not None:
                            progress.update(layer_tasks[layer_id], completed=current, total=total)

            progress.update(task_id, description=f"[green]Built {build_config['tag']}", completed=100)

            if self.upload_config.get('enabled', False):
                upload_task = progress.add_task(f"[cyan]Uploading {build_config['tag']}", total=100)
                self.upload_image(self.client.images.get(build_config['tag']), build_config)
                progress.update(upload_task, completed=100, description=f"[green]Uploaded {build_config['tag']}")

            return build_config['tag']
        except Exception as e:
            progress.update(task_id, description=f"[red]Error: {build_config['tag']} - {str(e)}")
            return None

    def build_all(self):
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn()
        )

        with Live(Panel(progress), refresh_per_second=10, console=self.console) as live:
            with ThreadPoolExecutor(max_workers=self.config.get('max_concurrent_builds', 3)) as executor:
                futures = {executor.submit(self.build_and_upload, build_config, progress): build_config for build_config in self.config['builds']}
                
                for future in as_completed(futures):
                    if self.killer.kill_now:
                        self.console.print("\n[yellow]Received interrupt signal. Stopping builds...[/yellow]")
                        executor.shutdown(wait=False)
                        return

                    build_config = futures[future]
                    result = future.result()

        self.console.print("[bold green]All builds completed.[/bold green]")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Docker Image Builder and Uploader")
    parser.add_argument("-c", "--config", default="config.yaml", help="Path to the configuration file (default: config.yaml)")
    parser.add_argument("-d", "--dockerfile", default="Dockerfile", help="Path to the Dockerfile (default: Dockerfile)")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without actually building or uploading images")
    parser.add_argument("--no-upload", action="store_true", help="Build images but do not upload them")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--max-concurrent", type=int, help="Maximum number of concurrent builds (overrides config file)")
    parser.add_argument("--list-presets", action="store_true", help="List available registry presets")
    return parser.parse_args()

def main():
    args = parse_arguments()

    if args.list_presets:
        print("Available registry presets:")
        for preset in DockerImageBuilder.REGISTRY_PRESETS:
            print(f"  - {preset}")
        return

    builder = DockerImageBuilder(dockerfile_path=args.dockerfile, config_path=args.config)

    if args.verbose:
        print(f"Using configuration file: {args.config}")
        print(f"Using Dockerfile: {args.dockerfile}")

    if args.dry_run:
        print("Performing dry run:")
        for build_config in builder.config['builds']:
            print(f"  Would build: {build_config['tag']}")
        return

    if args.no_upload:
        builder.upload_config['enabled'] = False
        print("Upload disabled. Images will be built but not uploaded.")

    if args.max_concurrent:
        builder.config['max_concurrent_builds'] = args.max_concurrent

    try:
        builder.build_all()
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt. Exiting...")

if __name__ == "__main__":
    main()