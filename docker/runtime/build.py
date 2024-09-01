#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
import signal
from typing import List, Iterator, NamedTuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import init, Fore, Style, Back
from datetime import datetime
import threading
import itertools
import shutil

# Initialize colorama for cross-platform colored output
init(autoreset=True)

class Context(NamedTuple):
    java: str
    type: str
    mcdr: str
    tag: str

class Logger:
    @staticmethod
    def log(level: str, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_colors = {
            "INFO": f"{Fore.WHITE}{Back.BLUE}",
            "SUCCESS": f"{Fore.WHITE}{Back.GREEN}",
            "ERROR": f"{Fore.WHITE}{Back.RED}",
            "WARN": f"{Fore.BLACK}{Back.YELLOW}"
        }
        level_color = level_colors.get(level, Fore.WHITE)
        print(f"{Fore.CYAN}[{timestamp}]{Style.RESET_ALL} {level_color}{level:^7}{Style.RESET_ALL} {message}")

class TUI:
    def __init__(self):
        self.tasks = {}
        self.lock = threading.Lock()
        self.spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])

    def add_task(self, task_id, description):
        with self.lock:
            self.tasks[task_id] = {"description": description, "status": "pending"}
        self.refresh()

    def update_task(self, task_id, status):
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]["status"] = status
        self.refresh()

    def refresh(self):
        terminal_width = shutil.get_terminal_size().columns
        with self.lock:
            sys.stdout.write("\033[2J\033[H")  # Clear screen and move cursor to top-left
            print(f"{Fore.CYAN}Docker Image Management{Style.RESET_ALL}".center(terminal_width))
            print("=" * terminal_width)
            for task_id, task in self.tasks.items():
                status_color = Fore.YELLOW
                status_symbol = next(self.spinner)
                if task["status"] == "success":
                    status_color = Fore.GREEN
                    status_symbol = "✔"
                elif task["status"] == "error":
                    status_color = Fore.RED
                    status_symbol = "✘"
                print(f"{status_color}{status_symbol}{Style.RESET_ALL} {task['description']}")
            sys.stdout.flush()

tui = TUI()

class CommandExecutor:
    @staticmethod
    def run_with_retry(cmd: List[str], task_id: str, max_retries: int = 3) -> subprocess.CompletedProcess:
        for attempt in range(max_retries):
            try:
                result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                tui.update_task(task_id, "success")
                return result
            except subprocess.CalledProcessError as e:
                tui.update_task(task_id, "error")
                if attempt < max_retries - 1:
                    time.sleep(5)  # Wait for 5 seconds before retrying
                else:
                    raise

    @staticmethod
    def execute(cmd: List[str], retry: int, task_id: str, description: str) -> bool:
        tui.add_task(task_id, description)
        try:
            CommandExecutor.run_with_retry(cmd, task_id, retry)
            return True
        except subprocess.CalledProcessError:
            return False

class DockerManager:
    @staticmethod
    def build_image(ctx: Context, args: argparse.Namespace) -> None:
        cmd = [
            "docker", "build", str(Path.cwd()),
            "-t", ctx.tag,
            "--build-arg", f"TYPE={ctx.type}",
            "--build-arg", f"JAVA={ctx.java}",
            "--build-arg", f"MCDR={ctx.mcdr}",
            "--build-arg", f"REGION={args.region}",
        ]

        if args.http_proxy:
            cmd.extend([
                "--build-arg", f"http_proxy={args.http_proxy}",
                "--build-arg", f"https_proxy={args.http_proxy}",
            ])

        task_id = f"build_{ctx.tag}"
        description = f"Building {ctx.type} image (Java: {ctx.java}, MCDR: {ctx.mcdr})"
        if CommandExecutor.execute(cmd, args.retry, task_id, description):
            if args.push:
                DockerManager.push_image(ctx.tag, args.retry)

    @staticmethod
    def push_image(tag: str, retry: int) -> None:
        task_id = f"push_{tag}"
        description = f"Pushing image: {tag}"
        CommandExecutor.execute(["docker", "push", tag], retry, task_id, description)

    @staticmethod
    def delete_image(tag: str, retry: int) -> None:
        task_id = f"delete_{tag}"
        description = f"Deleting image: {tag}"
        CommandExecutor.execute(["docker", "image", "rm", tag], retry, task_id, description)

class ContextGenerator:
    @staticmethod
    def iterate_all() -> Iterator[Context]:
        for java in ["8", "11", "17", "21"]:
            for type in ["general", "mcdr"]:
                if type == "general":
                    tag = f"bluefunny/pterodactyl:{type}-j{java}"
                    yield Context(java=java, type=type, mcdr="", tag=tag)
                if type == "mcdr":
                    for mcdr in ["latest", "2.13", "2.12", "2.11", "2.10"]:
                        tag = f"bluefunny/pterodactyl:{type}-j{java}-{mcdr}"
                        yield Context(java=java, type=type, mcdr=mcdr, tag=tag)

class ParallelExecutor:
    @staticmethod
    def execute(func, args_list, max_workers=None):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(func, *args) for args in args_list]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    Logger.log("ERROR", f"Generated an exception: {exc}")

class CommandHandler:
    @staticmethod
    def build(args: argparse.Namespace):
        ParallelExecutor.execute(DockerManager.build_image, [(ctx, args) for ctx in ContextGenerator.iterate_all()])

    @staticmethod
    def push(args: argparse.Namespace):
        ParallelExecutor.execute(DockerManager.push_image, [(ctx.tag, args.retry) for ctx in ContextGenerator.iterate_all()])

    @staticmethod
    def delete(args: argparse.Namespace):
        ParallelExecutor.execute(DockerManager.delete_image, [(ctx.tag, args.retry) for ctx in ContextGenerator.iterate_all()])

def signal_handler(signum, frame):
    Logger.log("WARN", "Operation interrupted. Cleaning up...")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Docker image management script for Pterodactyl",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s build china
  %(prog)s build global --http-proxy http://proxy.example.com:8080
  %(prog)s push
  %(prog)s delete
        """
    )
    parser.add_argument("-r", "--retry", type=int, default=3, help="Number of retries for failed operations (default: 3)")
    
    subparsers = parser.add_subparsers(title="Commands", dest="command", required=True, metavar="COMMAND")

    parser_build = subparsers.add_parser("build", help="Build all images")
    parser_build.add_argument("region", choices=["china", "global"], help="Specify the region for image source")
    parser_build.add_argument("-p", "--push", action="store_true", help="Push after build")
    parser_build.add_argument("--http-proxy", help="Set the URL of HTTP proxy to be used in build")

    subparsers.add_parser("push", help="Push all images")
    subparsers.add_parser("delete", help="Delete all images")

    args = parser.parse_args()

    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    try:
        if args.command == "build":
            CommandHandler.build(args)
        elif args.command == "push":
            CommandHandler.push(args)
        elif args.command == "delete":
            CommandHandler.delete(args)
    except Exception as e:
        Logger.log("ERROR", f"An unexpected error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
