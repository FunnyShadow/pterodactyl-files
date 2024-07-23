#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import time
from typing import Iterator, NamedTuple
from colorama import init, Fore, Style
from datetime import datetime

# Initialize colorama for cross-platform colored output
init()

class Context(NamedTuple):
    java: str
    type: str
    mcdr: str
    tag: str

def iterate_all() -> Iterator[Context]:
    for java in ["8", "11", "17", "21"]:
        for type in ["general", "mcdr"]:
            if type == "general":
                tag = f"bluefunny/pterodactyl:{type}-j{java}"
                yield Context(java=java, type=type, mcdr="", tag=tag)
            if type == "mcdr":
                for mcdr in ["latest", "2.12", "2.11", "2.10"]:
                    tag = f"bluefunny/pterodactyl:{type}-j{java}-{mcdr}"
                    yield Context(java=java, type=type, mcdr=mcdr, tag=tag)

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def print_log(level: str, message: str):
    timestamp = get_timestamp()
    if level == "INFO":
        level_color = Fore.BLUE
    elif level == "SUCCESS":
        level_color = Fore.GREEN
    elif level == "ERROR":
        level_color = Fore.RED
    else:
        level_color = Fore.WHITE
    
    print(f"{Fore.CYAN}[{timestamp}]{Style.RESET_ALL} {level_color}[{level}]{Style.RESET_ALL} {message}")

def print_info(message: str):
    print_log("INFO", message)

def print_success(message: str):
    print_log("SUCCESS", message)

def print_error(message: str):
    print_log("ERROR", message)

def run_command_with_retry(cmd: list[str], max_retries: int = 3) -> subprocess.CompletedProcess:
    for attempt in range(max_retries):
        try:
            return subprocess.run(cmd, check=True, stdout=sys.stdout, stderr=sys.stderr)
        except subprocess.CalledProcessError as e:
            print_error(f"Command failed with exit code {e.returncode}")
            print_error(f"Command: {' '.join(cmd)}")
            if attempt < max_retries - 1:
                print_info(f"Retrying... (Attempt {attempt + 1} of {max_retries})")
                time.sleep(5)  # Wait for 5 seconds before retrying
            else:
                print_error(f"Max retries reached. Command failed.")
                raise

def cmd_build(args: argparse.Namespace):
    for ctx in iterate_all():
        print_info(f"Building {ctx.type} image...")
        print_info(f"Java: {ctx.java}")
        if ctx.type == "mcdr":
            print_info(f"MCDR: {ctx.mcdr}")

        cmd = [
            "docker", "build", os.getcwd(),
            "-t", ctx.tag,
            "--build-arg", f"TYPE={ctx.type}",
            "--build-arg", f"JAVA={ctx.java}",
            "--build-arg", f"MCDR={ctx.mcdr}",
        ]

        if args.region:
            cmd.extend(["--build-arg", f"REGION={args.region}"])

        if args.http_proxy:
            cmd.extend([
                "--build-arg", f"http_proxy={args.http_proxy}",
                "--build-arg", f"https_proxy={args.http_proxy}",
            ])

        try:
            run_command_with_retry(cmd, args.retry)
            print_success(f"Successfully built image: {ctx.tag}")

            if args.push:
                cmd_push_single(ctx.tag, args.retry)
        except subprocess.CalledProcessError:
            print_error(f"Failed to build image: {ctx.tag}")
            continue

def cmd_push(args: argparse.Namespace):
    for ctx in iterate_all():
        cmd_push_single(ctx.tag, args.retry)

def cmd_push_single(tag: str, max_retries: int):
    print_info(f"Pushing image: {tag}")
    try:
        run_command_with_retry(["docker", "push", tag], max_retries)
        print_success(f"Successfully pushed image: {tag}")
    except subprocess.CalledProcessError:
        print_error(f"Failed to push image: {tag}")

def cmd_delete(args: argparse.Namespace):
    for ctx in iterate_all():
        print_info(f"Deleting image: {ctx.tag}")
        try:
            run_command_with_retry(["docker", "image", "rm", ctx.tag], args.retry)
            print_success(f"Successfully deleted image: {ctx.tag}")
        except subprocess.CalledProcessError:
            print_error(f"Failed to delete image: {ctx.tag}")

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
    
    subparsers = parser.add_subparsers(
        title="Commands",
        dest="command",
        required=True,
        metavar="COMMAND"
    )

    parser_build = subparsers.add_parser("build", help="Build all images")
    parser_build.add_argument("region", choices=["china", "global"], help="Specify the region for image source")
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
        print_error("\nOperation canceled by user")
        sys.exit(1)

if __name__ == "__main__":
    main()