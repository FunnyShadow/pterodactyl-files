import argparse
import concurrent.futures
import docker
import os
import signal
import sys
import threading
import time
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID
from rich.panel import Panel
from rich.table import Table
from datetime import datetime
from functools import wraps

# Global variables
console = Console()
client = docker.from_env()
stop_event = threading.Event()
log_lock = threading.Lock()
error_summary = []
error_summary_lock = threading.Lock()

def find_config_file():
    for filename in ['config.yml', 'config.yaml']:
        if os.path.exists(filename):
            return filename
    return None

def load_config(config_file):
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)
    
def format_log(func):
    @wraps(func)
    def wrapper(message, level="info"):
        timestamp = datetime.now().strftime("%Y-%m-%d [#66ccff]/ [/]%H:%M:%S")
        level_colors = {
            "info": "bold blue",
            "error": "bold red",
            "success": "bold green",
            "warning": "bold yellow"
        }
        level_text = level.upper().rjust(7)
        
        formatted_message = f"[#66ccff]{timestamp}[/] [green]|[/] [{level_colors[level]}]{level_text}[/] [yellow]->[/] {highlight_keywords(message)}"
        return func(formatted_message, level)
    
    return wrapper

def highlight_keywords(message):
    keywords = {
        "build": "cyan",
        "push": "magenta",
        "delete": "red",
        "image": "green",
        "successfully": "bold green",
        "failed": "bold red",
        "retrying": "yellow",
    }
    
    for keyword, color in keywords.items():
        message = message.replace(keyword, f"[{color}]{keyword}[/]")
    
    return message
    
@format_log
def log(message, level="info"):
    # 原有的 log 函数代码保持不变
    with log_lock:
        if level == "info":
            console.print(f"[bold blue]INFO:[/bold blue] {message}")
        elif level == "error":
            console.print(f"[bold red]ERROR:[/bold red] {message}")
        elif level == "success":
            console.print(f"[bold green]SUCCESS:[/bold green] {message}")
        elif level == "warning":
            console.print(f"[bold yellow]WARNING:[/bold yellow] {message}")

def add_to_error_summary(message):
    with error_summary_lock:
        error_summary.append(message)

def build_image(build_config, global_config, progress, task_id):
    tag = build_config['tag']
    build_type = build_config.get('build_type', 'vanilla')
    region = build_config.get('region', global_config.get('region', 'global'))
    build_dir = build_config.get('build_dir', global_config.get('build_dir', '.'))
    build_args = build_config.get('build_args', {})
    max_retries = global_config.get('max_retries', 3)
    retry_delay = global_config.get('retry_delay', 5)
    no_cache = global_config.get('no_cache', False)

    if region not in ['global', 'china']:
        log(f"Invalid region '{region}' for {tag}. Using 'global'.", "warning")
        region = 'global'

    dockerfile = f"Dockerfile"
    build_args['REGION'] = region
    build_args['TYPE'] = build_type

    for attempt in range(max_retries):
        try:
            log(f"Building image: {tag} (Attempt {attempt + 1}/{max_retries})")
            image, logs = client.images.build(
                path=build_dir,
                dockerfile=dockerfile,
                tag=tag,
                buildargs=build_args,
                quiet=False,
                nocache=no_cache
            )
            for line in logs:
                if 'stream' in line:
                    log(line['stream'].strip())
                progress.update(task_id, advance=1)
            log(f"Successfully built image: {tag}", "success")
            return True
        except Exception as e:
            log(f"Failed to build image {tag}: {str(e)}", "error")
            if attempt < max_retries - 1:
                log(f"Retrying in {retry_delay} seconds...", "warning")
                time.sleep(retry_delay)
            else:
                add_to_error_summary(f"Failed to build image {tag} after {max_retries} attempts: {str(e)}")
                return False

def push_image(tag, config):
    max_retries = config.get('max_retries', 3)
    retry_delay = config.get('retry_delay', 5)
    username = config['upload'].get('username')
    password = config['upload'].get('password')
    registry = config['upload'].get('registry')

    for attempt in range(max_retries):
        try:
            log(f"Pushing image: {tag} (Attempt {attempt + 1}/{max_retries})")
            auth_config = {}
            if username and password:
                auth_config = {'username': username, 'password': password}
            if registry:
                repository = f"{registry}/{tag}"
            else:
                repository = tag
            client.images.push(repository, auth_config=auth_config)
            log(f"Successfully pushed image: {tag}", "success")
            return True
        except Exception as e:
            log(f"Failed to push image {tag}: {str(e)}", "error")
            if attempt < max_retries - 1:
                log(f"Retrying in {retry_delay} seconds...", "warning")
                time.sleep(retry_delay)
            else:
                add_to_error_summary(f"Failed to push image {tag} after {max_retries} attempts: {str(e)}")
                return False

def delete_image(tag, config):
    max_retries = config.get('max_retries', 3)
    retry_delay = config.get('retry_delay', 5)
    force = config.get('force_delete', False)
    prune = config.get('prune_after_delete', False)

    for attempt in range(max_retries):
        try:
            log(f"Deleting image: {tag} (Attempt {attempt + 1}/{max_retries})")
            client.images.remove(tag, force=force)
            log(f"Successfully deleted image: {tag}", "success")
            if prune:
                client.images.prune()
                log("Pruned dangling images", "info")
            return True
        except Exception as e:
            log(f"Failed to delete image {tag}: {str(e)}", "error")
            if attempt < max_retries - 1:
                log(f"Retrying in {retry_delay} seconds...", "warning")
                time.sleep(retry_delay)
            else:
                add_to_error_summary(f"Failed to delete image {tag} after {max_retries} attempts: {str(e)}")
                return False

def run_tasks(config, action, tags=None):
    max_workers = config.get('max_parallel_tasks', 5)
    builds = config['build']

    if tags:
        builds = [b for b in builds if b['tag'] in tags]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        tasks = []
        for build in builds:
            task_id = progress.add_task(f"[cyan]{build['tag']}", total=100)
            tasks.append((build, task_id))

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            if action == 'build':
                futures = [executor.submit(build_image, build, config, progress, task_id) for build, task_id in tasks]
            elif action == 'push':
                futures = [executor.submit(push_image, build['tag'], config) for build, _ in tasks]
            elif action == 'delete':
                futures = [executor.submit(delete_image, build['tag'], config) for build, _ in tasks]

            for future in concurrent.futures.as_completed(futures):
                if stop_event.is_set():
                    for f in futures:
                        f.cancel()
                    break
                future.result()

def signal_handler(signum, frame):
    log("Received interrupt signal. Stopping tasks...", "info")
    stop_event.set()

def print_error_summary():
    if error_summary:
        console.print("\n[bold red]Error Summary:[/bold red]")
        for error in error_summary:
            console.print(f"- {error}")
    else:
        console.print("\n[bold green]No errors occurred during execution.[/bold green]")

def main():
    parser = argparse.ArgumentParser(description="Docker image builder and manager")
    parser.add_argument('-c', '--config', help='Path to the configuration file')
    subparsers = parser.add_subparsers(dest='action', required=True)

    build_parser = subparsers.add_parser('build', help='Build Docker images')
    build_parser.add_argument('-t', '--tags', nargs='+', help='Specific image tags to build')
    build_parser.add_argument('-r', '--region', choices=['global', 'china'], help='Specify the region for building')
    build_parser.add_argument('-d', '--build-dir', help='Specify the build directory')
    build_parser.add_argument('-a', '--build-arg', action='append', nargs=2, metavar=('KEY', 'VALUE'), help='Set a build-time variable')
    build_parser.add_argument('--no-cache', action='store_true', help='Do not use cache when building the image')

    push_parser = subparsers.add_parser('push', help='Push Docker images')
    push_parser.add_argument('-t', '--tags', nargs='+', help='Specific image tags to push')
    push_parser.add_argument('-u', '--username', help='Docker registry username')
    push_parser.add_argument('-p', '--password', help='Docker registry password')
    push_parser.add_argument('--registry', help='Specify a custom registry URL')

    delete_parser = subparsers.add_parser('delete', help='Delete Docker images')
    delete_parser.add_argument('-t', '--tags', nargs='+', help='Specific image tags to delete')
    delete_parser.add_argument('-f', '--force', action='store_true', help='Force removal of the image')
    delete_parser.add_argument('--prune', action='store_true', help='Remove all dangling images after deletion')

    args = parser.parse_args()

    if args.config:
        config_file = args.config
    else:
        config_file = find_config_file()
        if not config_file:
            log("No configuration file found. Please provide a config file using -c or --config option.", "error")
            sys.exit(1)

    try:
        config = load_config(config_file)
    except Exception as e:
        log(f"Failed to load configuration: {str(e)}", "error")
        sys.exit(1)

    # Update config with command-line arguments
    if args.action == 'build':
        if args.region:
            config['region'] = args.region
        if args.build_dir:
            config['build_dir'] = args.build_dir
        if args.build_arg:
            config['build_args'] = dict(args.build_arg)
        config['no_cache'] = args.no_cache
    elif args.action == 'push':
        if args.username:
            config['upload']['username'] = args.username
        if args.password:
            config['upload']['password'] = args.password
        if args.registry:
            config['upload']['registry'] = args.registry
    elif args.action == 'delete':
        config['force_delete'] = args.force
        config['prune_after_delete'] = args.prune

    signal.signal(signal.SIGINT, signal_handler)

    run_tasks(config, args.action, args.tags)

    if not stop_event.is_set():
        log("All tasks completed.", "success")
    else:
        log("Tasks were interrupted.", "info")

    print_error_summary()

if __name__ == "__main__":
    main()
