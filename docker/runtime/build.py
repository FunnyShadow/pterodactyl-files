#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
from typing import List, Iterator, NamedTuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import init, Fore, Style, Back
from datetime import datetime

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

class CommandExecutor:
    @staticmethod
    def run_with_retry(cmd: List[str], max_retries: int = 3) -> subprocess.CompletedProcess:
        for attempt in range(max_retries):
            try:
                return subprocess.run(cmd, check=True, stdout=sys.stdout, stderr=sys.stderr)
            except subprocess.CalledProcessError as e:
                Logger.log("ERROR", f"Command failed with exit code {e.returncode}")
                Logger.log("ERROR", f"Command: {' '.join(cmd)}")
                if attempt < max_retries - 1:
                    Logger.log("WARN", f"Retrying... (Attempt {attempt + 1} of {max_retries})")
                    time.sleep(5)  # Wait for 5 seconds before retrying
                else:
                    Logger.log("ERROR", "Max retries reached. Command failed.")
                    raise

    @staticmethod
    def execute(cmd: List[str], retry: int, success_msg: str, error_msg: str) -> bool:
        try:
            CommandExecutor.run_with_retry(cmd, retry)
            Logger.log("SUCCESS", success_msg)
            return True
        except subprocess.CalledProcessError:
            Logger.log("ERROR", error_msg)
            return False

class DockerManager:
    @staticmethod
    def build_image(ctx: Context, args: argparse.Namespace) -> None:
        Logger.log("INFO", f"Building {ctx.type} image (Java: {ctx.java}, MCDR: {ctx.mcdr})")

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

        if CommandExecutor.execute(cmd, args.retry, f"Successfully built image: {ctx.tag}", f"Failed to build image: {ctx.tag}"):
            if args.push:
                DockerManager.push_image(ctx.tag, args.retry)

    @staticmethod
    def push_image(tag: str, retry: int) -> None:
        Logger.log("INFO", f"Pushing image: {tag}")
        CommandExecutor.execute(["docker", "push", tag], retry, f"Successfully pushed image: {tag}", f"Failed to push image: {tag}")

    @staticmethod
    def delete_image(tag: str, retry: int) -> None:
        Logger.log("INFO", f"Deleting image: {tag}")
        CommandExecutor.execute(["docker", "image", "rm", tag], retry, f"Successfully deleted image: {tag}", f"Failed to delete image: {tag}")

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

    try:
        if args.command == "build":
            CommandHandler.build(args)
        elif args.command == "push":
            CommandHandler.push(args)
        elif args.command == "delete":
            CommandHandler.delete(args)
    except KeyboardInterrupt:
        Logger.log("ERROR", "Operation canceled by user")
        sys.exit(1)

if __name__ == "__main__":
    main()
