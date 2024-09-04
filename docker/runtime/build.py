import os
import yaml
import docker
import tempfile
import shutil
import argparse
import signal
import sys
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
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
        "dockerhub": "",
        "ghcr": "ghcr.io",
        "acr": "azurecr.io",
        "ecr": "amazonaws.com",
        "gcr": "gcr.io",
    }

    def __init__(self, dockerfile_path="Dockerfile", config_path="config.yaml"):
        self.dockerfile_path = dockerfile_path
        self.config_path = config_path
        self.client = docker.from_env()
        self.config = self._load_config()
        self.region = self.config.get("region", "global")
        self.upload_config = self.config.get("upload", {})
        self.killer = GracefulKiller()
        self.console = Console()

    def _load_config(self):
        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)

    def _prepare_build_context(self, build_config):
        temp_dir = tempfile.mkdtemp()
        shutil.copy2(self.dockerfile_path, temp_dir)
        return temp_dir

    def _parse_progress(self, line):
        progress_pattern = r"(\d+(?:\.\d+)?[KMG]?B?)/(\d+(?:\.\d+)?[KMG]?B?)"
        match = re.search(progress_pattern, line)
        if match:
            current, total = match.groups()
            return self._convert_size_to_bytes(current), self._convert_size_to_bytes(total)
        return None, None

    def _convert_size_to_bytes(self, size_str):
        units = {"K": 1024, "M": 1024**2, "G": 1024**3}
        if size_str[-1] in units:
            return int(float(size_str[:-1]) * units[size_str[-1]])
        elif size_str.endswith("B"):
            return int(float(size_str[:-1]))
        else:
            return int(float(size_str))

    def _update_layer_progress(self, line, layer_tasks, progress):
        if "Pulling from" in line["status"]:
            layer_id = line["status"].split()[-1]
            layer_tasks[layer_id] = progress.add_task(f"[magenta]Pulling {layer_id}", total=100)
        elif "Pull complete" in line["status"]:
            layer_id = line["status"].split()[0]
            if layer_id in layer_tasks:
                progress.update(layer_tasks[layer_id], completed=100)
        if "progress" in line:
            layer_id = line["id"]
            if layer_id in layer_tasks:
                current, total = self._parse_progress(line["progress"])
                if current is not None and total is not None:
                    progress.update(layer_tasks[layer_id], completed=current, total=total)

    def build_all(self):
        self.console = Console()
        build_tasks = []

        with Live(self.generate_output(build_tasks), refresh_per_second=10, console=self.console) as live:
            with ThreadPoolExecutor(max_workers=self.config.get("max_concurrent_builds", 3)) as executor:
                futures = {executor.submit(self.build_image, build_config): build_config for build_config in self.config["builds"]}

                for future in as_completed(futures):
                    if self.killer.kill_now:
                        self.console.print("\n[yellow]Received interrupt signal. Stopping builds...[/yellow]")
                        executor.shutdown(wait=False)
                        return

                    build_config = futures[future]
                    result = future.result()
                    if result:
                        build_tasks.append(result)
                    live.update(self.generate_output(build_tasks))

        self.console.print("[bold green]All builds completed.[/bold green]")

        if self.upload_config.get("auto_push", False):
            self.push_images()

    def build_image(self, build_config):
        context_path = self._prepare_build_context(build_config)
        tag = build_config["tag"]
        start_time = time.time()
        logs = []

        try:
            build_args = build_config.get("build_args", {})
            build_args["REGION"] = build_config.get("region", self.region)

            for line in self.client.api.build(
                path=context_path,
                dockerfile=os.path.basename(self.dockerfile_path),
                tag=tag,
                buildargs=build_args,
                rm=True,
                decode=True,
            ):
                if self.killer.kill_now:
                    return None

                if "stream" in line:
                    logs.append(line["stream"].strip())
                elif "error" in line:
                    raise Exception(line["error"])

            end_time = time.time()
            duration = end_time - start_time
            return {"tag": tag, "status": "success", "duration": duration, "logs": logs}
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            self.console.print(f"[bold red]Error occurred while building {tag}:[/bold red]")
            self.console.print_exception(show_locals=True)
            return {"tag": tag, "status": "error", "duration": duration, "logs": logs + [str(e)]}
        finally:
            shutil.rmtree(context_path)

    def push_images(self):
        if not self.upload_config.get("enabled", False):
            self.console.print("[yellow]Upload is not enabled in the configuration.[/yellow]")
            return

        upload_tasks = []

        with Live(self.generate_upload_output(upload_tasks), refresh_per_second=10, console=self.console) as live:
            for build_config in self.config["builds"]:
                tag = build_config["tag"]
                task = {
                    'tag': tag,
                    'status': 'uploading',
                    'start_time': time.time(),
                    'logs': []
                }
                upload_tasks.append(task)
                live.update(self.generate_upload_output(upload_tasks))

                try:
                    self._upload_image(tag, build_config, task)
                    task['status'] = 'success'
                except docker.errors.ImageNotFound:
                    task['status'] = 'error'
                    task['logs'].append(f"Image not found: {tag}")
                except Exception as e:
                    task['status'] = 'error'
                    task['logs'].append(f"Error uploading {tag}: {str(e)}")

                task['end_time'] = time.time()
                live.update(self.generate_upload_output(upload_tasks))

        self.console.print("[bold green]Upload process completed.[/bold green]")

    def _upload_image(self, tag, build_config, task):
        repository = self.upload_config.get("repository", "")
        if repository:
            remote_tag = f"{repository}/{tag}"
            self.client.images.get(tag).tag(remote_tag)
            tag = remote_tag

        for line in self.client.images.push(tag, stream=True, decode=True):
            if 'status' in line:
                task['logs'].append(line['status'])
            elif 'error' in line:
                raise Exception(line['error'])

    def delete_images(self):
        deleted_images = []
        for build_config in self.config["builds"]:
            tag = build_config["tag"]
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

    def generate_output(self, build_tasks):
        columns = []
        for task in build_tasks:
            if task["status"] == "success":
                text = Text(f"Successful build {task['tag']} -> {self.format_duration(task['duration'])}", style="green")
            else:
                text = Text(f"Failed build {task['tag']} -> {self.format_duration(task['duration'])}", style="red")
            columns.append(text)

        active_builds = [task for task in build_tasks if task["status"] not in ["success", "error"]]
        for task in active_builds:
            text = Text(f"Building {task['tag']} -> {self.format_duration(time.time() - task['start_time'])}\n")
            text.append("\n".join(task["logs"][-5:]))  # Show last 5 log lines
            columns.append(text)

        return Panel(Columns(columns))
    
    def generate_upload_output(self, upload_tasks):
        columns = []
        for task in upload_tasks:
            if task['status'] == 'success':
                text = Text(f"Successful upload {task['tag']} -> {self.format_duration(task['end_time'] - task['start_time'])}", style="green")
            elif task['status'] == 'error':
                text = Text(f"Failed upload {task['tag']} -> {self.format_duration(task['end_time'] - task['start_time'])}", style="red")
            else:
                text = Text(f"Uploading {task['tag']} -> {self.format_duration(time.time() - task['start_time'])}\n")
                text.append("\n".join(task['logs'][-5:]))  # Show last 5 log lines
            columns.append(text)
        
        return Panel(Columns(columns))

    def format_duration(self, seconds):
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def parse_arguments():
    parser = argparse.ArgumentParser(description="Build, upload, push, or delete Docker images based on configuration.")
    parser.add_argument("-d", "--dockerfile", default="Dockerfile", help="Path to the Dockerfile")
    parser.add_argument("-c", "--config", default="config.yaml", help="Path to the configuration file")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("build", help="Build and optionally upload Docker images")
    subparsers.add_parser("push", help="Push built Docker images to registry")
    subparsers.add_parser("delete", help="Delete built Docker images")

    return parser.parse_args()


def main():
    args = parse_arguments()
    try:
        builder = DockerImageBuilder(args.dockerfile, args.config)

        if args.command == "build":
            builder.build_all()
        elif args.command == "push":
            builder.push_images()
        elif args.command == "delete":
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
