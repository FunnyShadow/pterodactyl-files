import argparse
import concurrent.futures
import docker
import os
import signal
import sys
import threading
import time
import yaml
import queue
from rich.console import Console
from datetime import datetime
from functools import wraps

# Global variables
console = Console()
client = docker.from_env()
stop_event = threading.Event()
log_lock = threading.Lock()
log_queue = queue.Queue()
thread_local = threading.local()
sigint_count = 0


# Config
def find_config_file():
    for filename in ["config.yml", "config.yaml"]:
        if os.path.exists(filename):
            return filename
    return None


def load_config(config_file):
    with open(config_file, "r") as f:
        return yaml.safe_load(f)


# Logging
def log_worker():
    while True:
        log_entry = log_queue.get()
        if log_entry is None:
            break
        console.print(log_entry, soft_wrap=True)
        log_queue.task_done()


log_thread = threading.Thread(target=log_worker, daemon=True)
log_thread.start()


def set_task_name(name):
    thread_local.task_name = name


def get_task_name():
    return getattr(thread_local, "task_name", "Unknown")


def format_log(func):
    @wraps(func)
    def wrapper(message, level="info"):
        timestamp = datetime.now().strftime("%Y-%m-%d [#66ccff]/ [white]%H:%M:%S")
        level_colors = {
            "info": "bold blue",
            "error": "bold red",
            "success": "bold green",
            "warning": "bold yellow",
        }
        level_text = level.upper().rjust(7)
        task_name = get_task_name()
        if len(task_name) > 25:
            task_name = task_name[:22] + "..."
        task_name = task_name.ljust(25)

        formatted_message = f"[#66ccff]{timestamp}[/] [green]|[/] [purple]{task_name}[/] [green]|[/] [{level_colors[level]}]{level_text}[/] [yellow]->[/] {message}"
        log_queue.put(formatted_message)

    return wrapper



@format_log
def log(message, level="info"):
    pass


def cleanup_logging():
    log_queue.put(None)
    log_thread.join()


# Image Building
def build_image(build_config, global_config):
    set_task_name(build_config["tag"])
    tag = build_config["tag"]
    build_type = build_config.get("build_type", "vanilla")
    region = build_config.get("region", global_config.get("region", "global"))
    build_dir = build_config.get("build_dir", global_config.get("build_dir", "."))
    build_args = build_config.get("build_args", {})
    max_retries = global_config.get("max_retries", 3)
    retry_delay = global_config.get("retry_delay", 5)
    no_cache = global_config.get("no_cache", False)

    if region not in ["global", "china"]:
        log(f"Invalid region '{region}' for {tag}. Using 'global'.", "warning")
        region = "global"

    dockerfile = f"Dockerfile"
    build_args["REGION"] = region
    build_args["TYPE"] = build_type

    for attempt in range(max_retries):
        try:
            log(f"Building image: {tag} (Attempt {attempt + 1}/{max_retries})")
            image, logs = client.images.build(
                path=build_dir,
                dockerfile=dockerfile,
                tag=tag,
                buildargs=build_args,
                quiet=False,
                nocache=no_cache,
            )
            for line in logs:
                if "stream" in line:
                    log(line["stream"].strip())
            log(f"Successfully built image: {tag}", "success")
            return True
        except Exception as e:
            log(f"Failed to build image {tag}: {str(e)}", "error")
            if attempt < max_retries - 1:
                log(f"Retrying in {retry_delay} seconds...", "warning")
                time.sleep(retry_delay)
            else:
                return False


# Image pushing
def push_image(tag, config):
    set_task_name(tag)
    max_retries = config.get("max_retries", 3)
    retry_delay = config.get("retry_delay", 5)
    username = config["upload"].get("username")
    password = config["upload"].get("password")
    registry = config["upload"].get("registry")

    for attempt in range(max_retries):
        try:
            log(f"Pushing image: {tag} (Attempt {attempt + 1}/{max_retries})")
            auth_config = {}
            if username and password:
                auth_config = {"username": username, "password": password}
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
                return False


# Image deleting
def delete_image(tag, config):
    set_task_name(tag)
    force = config.get("force_delete", False)
    prune = config.get("prune_after_delete", False)

    try:
        # Check if the image exists
        client.images.get(tag)

        log(f"Deleting image: {tag}")
        client.images.remove(tag, force=force)
        log(f"Successfully deleted image: {tag}", "success")
        if prune:
            client.images.prune()
            log("Pruned dangling images", "info")
        return True
    except docker.errors.ImageNotFound:
        log(f"Image {tag} not found. Skipping deletion.", "warning")
        return False
    except Exception as e:
        log(f"Failed to delete image {tag}: {str(e)}", "error")
        return False


# Parallel tasks
def run_tasks(config, action, tags=None):
    max_workers = config.get("max_parallel_tasks", 5)
    builds = config["build"]

    if tags:
        builds = [b for b in builds if b["tag"] in tags]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        if action == "build":
            futures = [executor.submit(build_image, build, config) for build in builds]
        elif action == "push":
            futures = [
                executor.submit(push_image, build["tag"], config) for build in builds
            ]
        elif action == "delete":
            futures = [
                executor.submit(delete_image, build["tag"], config) for build in builds
            ]

        for future in concurrent.futures.as_completed(futures):
            if stop_event.is_set():
                for f in futures:
                    f.cancel()
                executor.shutdown(wait=False)
                break
            future.result()

    if stop_event.is_set():
        log("Graceful shutdown completed.", "info")


# Signal handling
def signal_handler(signum, frame):
    global sigint_count
    sigint_count += 1

    if sigint_count == 1:
        log(
            "Received interrupt signal. Attempting graceful shutdown. Press Ctrl+C again to force quit.",
            "warning",
        )
        stop_event.set()
    else:
        log("Received second interrupt signal. Forcing immediate shutdown.", "error")
        os._exit(1)


def main():
    parser = argparse.ArgumentParser(description="Docker image builder and manager")
    parser.add_argument("-c", "--config", help="Path to the configuration file")
    subparsers = parser.add_subparsers(dest="action", required=True)

    build_parser = subparsers.add_parser("build", help="Build Docker images")
    build_parser.add_argument(
        "-t", "--tags", nargs="+", help="Specific image tags to build"
    )
    build_parser.add_argument(
        "-r",
        "--region",
        choices=["global", "china"],
        help="Specify the region for building",
    )
    build_parser.add_argument("-d", "--build-dir", help="Specify the build directory")
    build_parser.add_argument(
        "-a",
        "--build-arg",
        action="append",
        nargs=2,
        metavar=("KEY", "VALUE"),
        help="Set a build-time variable",
    )
    build_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Do not use cache when building the image",
    )

    push_parser = subparsers.add_parser("push", help="Push Docker images")
    push_parser.add_argument(
        "-t", "--tags", nargs="+", help="Specific image tags to push"
    )
    push_parser.add_argument("-u", "--username", help="Docker registry username")
    push_parser.add_argument("-p", "--password", help="Docker registry password")
    push_parser.add_argument("--registry", help="Specify a custom registry URL")

    delete_parser = subparsers.add_parser("delete", help="Delete Docker images")
    delete_parser.add_argument(
        "-t", "--tags", nargs="+", help="Specific image tags to delete"
    )
    delete_parser.add_argument(
        "-f", "--force", action="store_true", help="Force removal of the image"
    )
    delete_parser.add_argument(
        "--prune", action="store_true", help="Remove all dangling images after deletion"
    )

    args = parser.parse_args()

    if args.config:
        config_file = args.config
    else:
        config_file = find_config_file()
        if not config_file:
            log(
                "No configuration file found. Please provide a config file using -c or --config option.",
                "error",
            )
            cleanup_logging()
            sys.exit(1)

    try:
        config = load_config(config_file)
    except Exception as e:
        log(f"Failed to load configuration: {str(e)}", "error")
        cleanup_logging()
        sys.exit(1)

    # Update config with command-line arguments
    if args.action == "build":
        if args.region:
            config["region"] = args.region
        if args.build_dir:
            config["build_dir"] = args.build_dir
        if args.build_arg:
            config["build_args"] = dict(args.build_arg)
        config["no_cache"] = args.no_cache
    elif args.action == "push":
        if args.username:
            config["upload"]["username"] = args.username
        if args.password:
            config["upload"]["password"] = args.password
        if args.registry:
            config["upload"]["registry"] = args.registry
    elif args.action == "delete":
        config["force_delete"] = args.force
        config["prune_after_delete"] = args.prune

    signal.signal(signal.SIGINT, signal_handler)

    try:
        run_tasks(config, args.action, args.tags)
    except KeyboardInterrupt:
        pass

    if stop_event.is_set():
        log(
            "Tasks were interrupted. Attempting to finish ongoing operations...",
            "warning",
        )
        time.sleep(5)
    else:
        log("All tasks completed.", "success")

    cleanup_logging()

    if sigint_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    log_thread = threading.Thread(target=log_worker, daemon=True)
    log_thread.start()
    main()
