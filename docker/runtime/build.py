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
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.traceback import install as install_rich_traceback

# Install rich traceback handler
install_rich_traceback(show_locals=True)

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

    def build_image(self, build_config, progress):
        context_path = self.prepare_build_context(build_config)
        task_id = progress.add_task(f"[cyan]Building {build_config['tag']}", total=100)
        layer_tasks = {}
        
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
                if self.killer.kill_now:
                    return None

                if 'stream' in line:
                    progress.update(task_id, description=f"[cyan]Building {build_config['tag']}: {line['stream'].strip()}")
                elif 'status' in line:
                    if 'Pulling from' in line['status']:
                        layer_id = line['status'].split()[-1]
                        layer_tasks[layer_id] = progress.add_task(f"[magenta]Pulling {layer_id}", total=100)
                    elif 'Pull complete' in line['status']:
                        layer_id = line['status'].split()[0]
                        if layer_id in layer_tasks:
                            progress.update(layer_tasks[layer_id], completed=100)
                    if 'progress' in line:
                        layer_id = line['id']
                        if layer_id in layer_tasks:
                            current, total = self.parse_progress(line['progress'])
                            if current is not None and total is not None:
                                progress.update(layer_tasks[layer_id], completed=current, total=total)
                elif 'error' in line:
                    raise Exception(line['error'])

            progress.update(task_id, description=f"[green]Built {build_config['tag']}", completed=100)
            return build_config['tag']
        except Exception as e:
            progress.update(task_id, description=f"[red]Error: {build_config['tag']}")
            self.console.print(f"[bold red]Error occurred while building {build_config['tag']}:[/bold red]")
            self.console.print_exception(show_locals=True)
            return None
        finally:
            shutil.rmtree(context_path)

    def build_all(self):
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn()
        )

        with Live(Panel(progress), refresh_per_second=10, console=self.console) as live:
            with ThreadPoolExecutor(max_workers=self.config.get('max_concurrent_builds', 3)) as executor:
                futures = {executor.submit(self.build_image, build_config, progress): build_config for build_config in self.config['builds']}
                
                for future in as_completed(futures):
                    if self.killer.kill_now:
                        self.console.print("\n[yellow]Received interrupt signal. Stopping builds...[/yellow]")
                        executor.shutdown(wait=False)
                        return

                    build_config = futures[future]
                    result = future.result()

        self.console.print("[bold green]All builds completed.[/bold green]")

        if self.upload_config.get('auto_push', False):
            self.push_images()

    def push_images(self):
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn()
        )

        with Live(Panel(progress), refresh_per_second=10, console=self.console) as live:
            for build_config in self.config['builds']:
                tag = build_config['tag']
                task_id = progress.add_task(f"[cyan]Uploading {tag}", total=100)
                try:
                    self.upload_image(self.client.images.get(tag), build_config)
                    progress.update(task_id, completed=100, description=f"[green]Uploaded {tag}")
                except docker.errors.ImageNotFound:
                    progress.update(task_id, description=f"[red]Image not found: {tag}")
                except Exception as e:
                    progress.update(task_id, description=f"[red]Error uploading {tag}: {str(e)}")

        self.console.print("[bold green]Upload process completed.[/bold green]")

    def push_images(self):
        if not self.upload_config.get('enabled', False):
            self.console.print("[yellow]Upload is not enabled in the configuration.[/yellow]")
            return

        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn()
        )

        with Live(Panel(progress), refresh_per_second=10, console=self.console) as live:
            for build_config in self.config['builds']:
                tag = build_config['tag']
                task_id = progress.add_task(f"[cyan]Uploading {tag}", total=100)
                try:
                    self.upload_image(self.client.images.get(tag), build_config)
                    progress.update(task_id, completed=100, description=f"[green]Uploaded {tag}")
                except docker.errors.ImageNotFound:
                    progress.update(task_id, description=f"[red]Image not found: {tag}")
                except Exception as e:
                    progress.update(task_id, description=f"[red]Error uploading {tag}: {str(e)}")

        self.console.print("[bold green]Upload process completed.[/bold green]")

    def delete_images(self):
            deleted_images = []
            for build_config in self.config['builds']:
                tag = build_config['tag']
                try:
                    self.client.images.remove(tag, force=True)
                    deleted_images.append(tag)
                    self.console.print(f"[green]Successfully deleted image: {tag}[/green]")
                except docker.errors.ImageNotFound:
                    self.console.print(f"[yellow]Image not found: {tag}[/yellow]")
                except Exception as e:
                    self.console.print(f"[red]Error deleting image {tag}: {str(e)}[/red]")
            
            if deleted_images:
                self.console.print(f"[bold green]Deleted {len(deleted_images)} image(s).[/bold green]")
            else:
                self.console.print("[yellow]No images were deleted.[/yellow]")

def parse_arguments():
    parser = argparse.ArgumentParser(description="Build, upload, push, or delete Docker images based on configuration.")
    parser.add_argument('-d', '--dockerfile', default='Dockerfile', help='Path to the Dockerfile')
    parser.add_argument('-c', '--config', default='config.yaml', help='Path to the configuration file')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Build command
    build_parser = subparsers.add_parser('build', help='Build and optionally upload Docker images')
    
    # Push command
    push_parser = subparsers.add_parser('push', help='Push built Docker images to registry')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete built Docker images')
    
    return parser.parse_args()

def main():
    args = parse_arguments()
    try:
        builder = DockerImageBuilder(args.dockerfile, args.config)
        
        if args.command == 'build':
            builder.build_all()
        elif args.command == 'push':
            builder.push_images()
        elif args.command == 'delete':
            builder.delete_images()
        else:
            builder.console.print("[yellow]No command specified. Use 'build', 'push', or 'delete'.[/yellow]")
    
    except Exception as e:
        console = Console()
        console.print("[bold red]An unexpected error occurred:[/bold red]")
        console.print_exception(show_locals=True)
        sys.exit(1)

if __name__ == "__main__":
    main()