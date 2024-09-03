#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import time
from typing import Iterator, NamedTuple
from colorama import init, Fore, Style, Back
from datetime import datetime

# Initialize colorama for cross-platform colored output
init(autoreset=True)

class Context(NamedTuple):
    java: str
    type: str
    mcdr: str
    tag: str

def iterate_all() -> Iterator[Context]:
    for java in ["8", "11", "17", "21"]:
        for type in ["general", "mcdr"]:
            if type == "general":
                tag = f"bluefunny/minecraft:{type}-j{java}"
                yield Context(java=java, type=type, mcdr="", tag=tag)
            if type == "mcdr":
                for mcdr in ["2.13", "2.12", "2.11", "2.10"]:
                    tag = f"bluefunny/minecraft:{type}-j{java}-{mcdr}"
                    yield Context(java=java, type=type, mcdr=mcdr, tag=tag)

def print_log(level: str, message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    level_colors = {
        "INFO": f"{Fore.WHITE}{Back.BLUE}",
        "SUCCESS": f"{Fore.WHITE}{Back.GREEN}",
        "ERROR": f"{Fore.WHITE}{Back.RED}",
        "WARN": f"{Fore.BLACK}{Back.YELLOW}"
    }
    level_color = level_colors.get(level, Fore.WHITE)
    print(f"{Fore.CYAN}[{timestamp}]{Style.RESET_ALL} {level_color}{level:^7}{Style.RESET_ALL} {message}")

def run_command_with_retry(cmd: list[str], max_retries: int = 3) -> subprocess.CompletedProcess:
    for attempt in range(max_retries):
        try:
            return subprocess.run(cmd, check=True, stdout=sys.stdout, stderr=sys.stderr)
        except subprocess.CalledProcessError as e:
            print_log("ERROR", f"Command failed with exit code {e.returncode}")
            print_log("ERROR", f"Command: {' '.join(cmd)}")
            if attempt < max_retries - 1:
                print_log("WARN", f"Retrying... (Attempt {attempt + 1} of {max_retries})")
                time.sleep(5)  # Wait for 5 seconds before retrying
            else:
                print_log("ERROR", "Max retries reached. Command failed.")
                raise

def execute_command(cmd: list[str], retry: int, success_msg: str, error_msg: str):
    try:
        run_command_with_retry(cmd, retry)
        print_log("SUCCESS", success_msg)
        return True
    except subprocess.CalledProcessError:
        print_log("ERROR", error_msg)
        return False

def cmd_build(args: argparse.Namespace):
    for ctx in iterate_all():
        print_log("INFO", f"Building {ctx.type} image (Java: {ctx.java}, MCDR: {ctx.mcdr})")

        cmd = [
            "docker", "build", os.getcwd(),
            "-t", ctx.tag,
            "--build-arg", f"TYPE={ctx.type}",
            "--build-arg", f"JAVA={ctx.java}",
            "--build-arg", f"MCDR={ctx.mcdr}",
        ]

        # Use global as default region if not specified
        region = args.region if args.region else "global"
        cmd.extend(["--build-arg", f"REGION={region}"])

        if args.http_proxy:
            cmd.extend([
                "--build-arg", f"http_proxy={args.http_proxy}",
                "--build-arg", f"https_proxy={args.http_proxy}",
            ])

        if execute_command(cmd, args.retry, f"Successfully built image: {ctx.tag}", f"Failed to build image: {ctx.tag}"):
            if args.push:
                cmd_push_single(ctx.tag, args.retry)

def cmd_push(args: argparse.Namespace):
    for ctx in iterate_all():
        cmd_push_single(ctx.tag, args.retry)

def cmd_push_single(tag: str, retry: int):
    print_log("INFO", f"Pushing image: {tag}")
    execute_command(["docker", "push", tag], retry, f"Successfully pushed image: {tag}", f"Failed to push image: {tag}")

def cmd_delete(args: argparse.Namespace):
    for ctx in iterate_all():
        # Check if the image exists before attempting to delete
        check_cmd = ["docker", "images", "-q", ctx.tag]
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        if result.stdout:
            print_log("INFO", f"Deleting image: {ctx.tag}")
            execute_command(["docker", "image", "rm", ctx.tag], args.retry, f"Successfully deleted image: {ctx.tag}", f"Failed to delete image: {ctx.tag}")
        else:
            print_log("WARN", f"Image not found: {ctx.tag}")

def main():
    parser = argparse.ArgumentParser(
        description="Docker image management script for Pterodactyl",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s build --region china
  %(prog)s build --region global --http-proxy http://proxy.example.com:8080
  %(prog)s build # Uses global as default region
  %(prog)s push
  %(prog)s delete
        """
    )
    parser.add_argument("-r", "--retry", type=int, default=3, help="Number of retries for failed operations (default: 3)")
    
    subparsers = parser.add_subparsers(title="Commands", dest="command", required=True, metavar="COMMAND")

    parser_build = subparsers.add_parser("build", help="Build all images")
    parser_build.add_argument("-r", "--region", choices=["china", "global"], help="Specify the region for image source (default: global)")
    parser_build.add_argument("-p", "--push", action="store_true", help="Push after build")
    parser_build.add_argument("--http-proxy", help="Set the URL of HTTP proxy to be used in build")

    subparsers.add_parser("push", help="Push all images")
    subparsers.add_parser("delete", help="Delete all images")

    args = parser.parse_args()

    try:
        if args.command == "build":
            cmd_build(args)
        elif args.command == "push":
            cmd_push(args)
        elif args.command == "delete":
            cmd_delete(args)
    except KeyboardInterrupt:
        print_log("ERROR", "Operation canceled by user")
        sys.exit(1)

if __name__ == "__main__":
    main()

