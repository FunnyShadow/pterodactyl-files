#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
import signal
from typing import List, Iterator, NamedTuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import asyncio
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Header, Footer, Static, ProgressBar, Button, Log
from textual.reactive import reactive
from textual import events

class Context(NamedTuple):
    java: str
    type: str
    mcdr: str
    tag: str

class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"

class Task:
    def __init__(self, id: str, description: str):
        self.id = id
        self.description = description
        self.status = TaskStatus.PENDING
        self.progress = 0.0
        self.log = []

    def update(self, status: str, progress: float = None):
        self.status = status
        if progress is not None:
            self.progress = progress

    def add_log(self, message: str):
        self.log.append(message)

class TaskManager:
    def __init__(self):
        self.tasks = {}

    def add_task(self, task: Task):
        self.tasks[task.id] = task

    def update_task(self, task_id: str, status: str, progress: float = None):
        if task_id in self.tasks:
            self.tasks[task_id].update(status, progress)

    def add_log(self, task_id: str, message: str):
        if task_id in self.tasks:
            self.tasks[task_id].add_log(message)

class TaskWidget(Static):
    def __init__(self, task: Task):
        super().__init__()
        self.task = task

    def render(self):
        status_color = {
            TaskStatus.PENDING: "yellow",
            TaskStatus.RUNNING: "blue",
            TaskStatus.SUCCESS: "green",
            TaskStatus.ERROR: "red"
        }.get(self.task.status, "white")

        return f"[{status_color}]{self.task.status:^8}[/] {self.task.description}"

class TaskGroupWidget(Static):
    def __init__(self, title: str):
        super().__init__()
        self.title = title

    def compose(self) -> ComposeResult:
        yield Static(f"[bold]{self.title}[/bold]")
        yield Container(id=f"{self.title.lower()}-tasks")

class DockerManagerTUI(App):
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, task_manager: TaskManager):
        super().__init__()
        self.task_manager = task_manager
        self.selected_task = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            TaskGroupWidget("General"),
            TaskGroupWidget("MCDR"),
            id="task-groups"
        )
        yield Static("Select a task to view its log", id="log-header")
        yield Log(id="task-log")
        yield Footer()

    def on_mount(self):
        self.update_tasks()

    def update_tasks(self):
        general_container = self.query_one("#general-tasks")
        mcdr_container = self.query_one("#mcdr-tasks")

        general_container.remove_children()
        mcdr_container.remove_children()

        for task in self.task_manager.tasks.values():
            task_widget = TaskWidget(task)
            if "general" in task.id:
                general_container.mount(task_widget)
            else:
                mcdr_container.mount(task_widget)

        self.refresh()

    def on_button_pressed(self, event: Button.Pressed):
        self.selected_task = event.button.id
        self.update_log()

    def update_log(self):
        if self.selected_task:
            task = self.task_manager.tasks.get(self.selected_task)
            if task:
                log_widget = self.query_one("#task-log")
                log_widget.clear()
                for line in task.log:
                    log_widget.write(line)

    async def update_ui(self):
        while True:
            self.update_tasks()
            self.update_log()
            await asyncio.sleep(0.1)

class CommandExecutor:
    @staticmethod
    async def run_with_retry(cmd: List[str], task_id: str, task_manager: TaskManager, max_retries: int = 3) -> subprocess.CompletedProcess:
        for attempt in range(max_retries):
            try:
                task_manager.update_task(task_id, TaskStatus.RUNNING)
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    task_manager.add_log(task_id, line.decode().strip())

                await process.wait()

                if process.returncode == 0:
                    task_manager.update_task(task_id, TaskStatus.SUCCESS, 1.0)
                    return process
                else:
                    raise subprocess.CalledProcessError(process.returncode, cmd)
            except subprocess.CalledProcessError as e:
                task_manager.update_task(task_id, TaskStatus.ERROR)
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)  # Wait for 5 seconds before retrying
                else:
                    raise

    @staticmethod
    async def execute(cmd: List[str], retry: int, task_id: str, description: str, task_manager: TaskManager) -> bool:
        task = Task(task_id, description)
        task_manager.add_task(task)
        try:
            await CommandExecutor.run_with_retry(cmd, task_id, task_manager, retry)
            return True
        except subprocess.CalledProcessError:
            return False

class DockerManager:
    @staticmethod
    async def build_image(ctx: Context, args: argparse.Namespace, task_manager: TaskManager) -> None:
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
        if await CommandExecutor.execute(cmd, args.retry, task_id, description, task_manager):
            if args.push:
                await DockerManager.push_image(ctx.tag, args.retry, task_manager)

    @staticmethod
    async def push_image(tag: str, retry: int, task_manager: TaskManager) -> None:
        task_id = f"push_{tag}"
        description = f"Pushing image: {tag}"
        await CommandExecutor.execute(["docker", "push", tag], retry, task_id, description, task_manager)

    @staticmethod
    async def delete_image(tag: str, retry: int, task_manager: TaskManager) -> None:
        task_id = f"delete_{tag}"
        description = f"Deleting image: {tag}"
        await CommandExecutor.execute(["docker", "image", "rm", tag], retry, task_id, description, task_manager)

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

async def run_tasks(func, args_list):
    tasks = [func(*args) for args in args_list]
    await asyncio.gather(*tasks)

class CommandHandler:
    @staticmethod
    async def build(args: argparse.Namespace, task_manager: TaskManager):
        await run_tasks(DockerManager.build_image, [(ctx, args, task_manager) for ctx in ContextGenerator.iterate_all()])

    @staticmethod
    async def push(args: argparse.Namespace, task_manager: TaskManager):
        await run_tasks(DockerManager.push_image, [(ctx.tag, args.retry, task_manager) for ctx in ContextGenerator.iterate_all()])

    @staticmethod
    async def delete(args: argparse.Namespace, task_manager: TaskManager):
        await run_tasks(DockerManager.delete_image, [(ctx.tag, args.retry, task_manager) for ctx in ContextGenerator.iterate_all()])

def signal_handler(signum, frame):
    print("Operation interrupted. Cleaning up...")
    sys.exit(1)

async def main():
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

    task_manager = TaskManager()
    tui = DockerManagerTUI(task_manager)

    try:
        async def run_command():
            if args.command == "build":
                await CommandHandler.build(args, task_manager)
            elif args.command == "push":
                await CommandHandler.push(args, task_manager)
            elif args.command == "delete":
                await CommandHandler.delete(args, task_manager)

        asyncio.create_task(run_command())
        asyncio.create_task(tui.update_ui())
        await tui.run_async()

    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
