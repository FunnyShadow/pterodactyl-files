#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from typing import Iterator, NamedTuple
from colorama import init, Fore, Style

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

def print_info(message: str):
    print(f"{Fore.CYAN}{message}{Style.RESET_ALL}")

def print_success(message: str):
    print(f"{Fore.GREEN}{message}{Style.RESET_ALL}")

def print_error(message: str):
    print(f"{Fore.RED}{message}{Style.RESET_ALL}", file=sys.stderr)

def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, check=check, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed with exit code {e.returncode}")
        print_error(f"Command: {' '.join(cmd)}")
        if e.stdout:
            print_error(f"stdout:\n{e.stdout}")
        if e.stderr:
            print_error(f"stderr:\n{e.stderr}")
        raise

def cmd_build(args: argparse.Namespace):
    for ctx in iterate_all():
        print_info(f"> Building {ctx.type} image...")
        print_info(f"> Java: {ctx.java}")
        if ctx.type == "mcdr":
            print_info(f"> MCDR: {ctx.mcdr}")

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

        run_command(cmd)
        print_success(f"Successfully built image: {ctx.tag}")

        if args.push:
            cmd_push_single(ctx.tag)

def cmd_push(args: argparse.Namespace):
    for ctx in iterate_all():
        cmd_push_single(ctx.tag)

def cmd_push_single(tag: str):
    print_info(f"Pushing image: {tag}")
    run_command(["docker", "push", tag])
    print_success(f"Successfully pushed image: {tag}")

def cmd_delete(args: argparse.Namespace):
    for ctx in iterate_all():
        print_info(f"Deleting image: {ctx.tag}")
        run_command(["docker", "image", "rm", ctx.tag])
        print_success(f"Successfully deleted image: {ctx.tag}")

def main():
    parser = argparse.ArgumentParser(
        description="Docker image management script for Pterodactyl",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s build -r china
  %(prog)s build --region global --http-proxy http://proxy.example.com:8080
  %(prog)s push
  %(prog)s delete
        """
    )
    subparsers = parser.add_subparsers(
        title="Commands",
        dest="command",
        required=True,
        metavar="COMMAND"
    )

    parser_build = subparsers.add_parser("build", help="Build all images")
    parser_build.add_argument("-p", "--push", action="store_true", help="Push after build")
    parser_build.add_argument("--http-proxy", help="Set the URL of HTTP proxy to be used in build")
    parser_build.add_argument("-r", "--region", choices=["china", "global"], help="Specify the region for image source")

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
    except subprocess.CalledProcessError:
        sys.exit(1)
    except KeyboardInterrupt:
        print_error("\nOperation canceled by user")
        sys.exit(1)

if __name__ == "__main__":
    main()