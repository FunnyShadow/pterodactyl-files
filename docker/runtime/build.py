#!/usr/bin/env python3
import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, run
from typing import Iterator, NamedTuple

from colorama import init, Fore

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
                tag = f"bluefunny/pterodactyl:{type}-j{java}"
                yield Context(java=java, type=type, mcdr="", tag=tag)
            if type == "mcdr":
                for mcdr in ["2.13", "2.12", "2.11", "2.10"]:
                    tag = f"bluefunny/pterodactyl:{type}-j{java}-{mcdr}"
                    yield Context(java=java, type=type, mcdr=mcdr, tag=tag)

def setup_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    return logger

logger = setup_logger()

def run_command(cmd: list[str], check: bool = True) -> CompletedProcess:
    try:
        return run(cmd, check=check, capture_output=True, text=True)
    except CalledProcessError as e:
        logger.error(f"{Fore.RED}Command failed with exit code {e.returncode}")
        logger.error(f"Command: {' '.join(cmd)}")
        if e.stdout:
            logger.error(f"stdout:\n{e.stdout}")
        if e.stderr:
            logger.error(f"stderr:\n{e.stderr}")
        raise

def build_image(ctx: Context, args: argparse.Namespace):
    logger.info(f"{Fore.CYAN}> Building {ctx.type} image...")
    logger.info(f"> Java: {ctx.java}")
    if ctx.type == "mcdr":
        logger.info(f"> MCDR: {ctx.mcdr}")

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

    run_command(cmd)
    logger.info(f"{Fore.GREEN}Successfully built image: {ctx.tag}")

    if args.push:
        push_image(ctx.tag)

def push_image(tag: str):
    logger.info(f"{Fore.CYAN}Pushing image: {tag}")
    run_command(["docker", "push", tag])
    logger.info(f"{Fore.GREEN}Successfully pushed image: {tag}")

def delete_image(tag: str):
    logger.info(f"{Fore.CYAN}Deleting image: {tag}")
    run_command(["docker", "image", "rm", tag])
    logger.info(f"{Fore.GREEN}Successfully deleted image: {tag}")

def parallel_execute(func, iterable, max_workers=4):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(func, item) for item in iterable]
        for future in as_completed(futures):
            try:
                future.result()
            except CalledProcessError:
                logger.error(f"{Fore.RED}An error occurred during execution")

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
            parallel_execute(partial(build_image, args=args), iterate_all())
        elif args.command == "push":
            parallel_execute(push_image, (ctx.tag for ctx in iterate_all()))
        elif args.command == "delete":
            parallel_execute(delete_image, (ctx.tag for ctx in iterate_all()))
    except KeyboardInterrupt:
        logger.error(f"{Fore.RED}\nOperation canceled by user")
        sys.exit(1)

if __name__ == "__main__":
    main()
