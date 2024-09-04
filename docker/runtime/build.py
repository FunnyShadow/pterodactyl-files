#!/usr/bin/env python3
import argparse
import os
import sys
import time
from typing import Dict, Callable
from datetime import datetime
import yaml
import docker
from colorama import init, Fore, Style, Back
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import logging
import base64
import boto3

init(autoreset=True)
stop_flag = threading.Event()


class ColoredFormatter(logging.Formatter):
    level_colors = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.WHITE,
        logging.WARNING: f"{Fore.BLACK}{Back.YELLOW}",
        logging.ERROR: f"{Fore.WHITE}{Back.RED}",
        logging.CRITICAL: f"{Fore.WHITE}{Back.RED}",
    }

    def format(self, record):
        levelname = record.levelname
        if record.levelno == logging.INFO:
            levelname = f"{Fore.WHITE}{Back.BLUE}{levelname:^7}{Style.RESET_ALL}"
        elif record.levelno == logging.WARNING:
            levelname = f"{Fore.BLACK}{Back.YELLOW}{levelname:^7}{Style.RESET_ALL}"
        elif record.levelno in (logging.ERROR, logging.CRITICAL):
            levelname = f"{Fore.WHITE}{Back.RED}{levelname:^7}{Style.RESET_ALL}"

        log_color = self.level_colors.get(record.levelno, "")
        log_fmt = f"{Fore.CYAN}[%(asctime)s]{Style.RESET_ALL} {levelname} {log_color}%(message)s{Style.RESET_ALL}"
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

logger = logging.getLogger("DockerScript")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter())
logger.addHandler(console_handler)

def load_config(config_file: str) -> Dict:
    try:
        with open(config_file, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_file}")
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing config file: {e}")
        sys.exit(1)


def retry_operation(operation: Callable, *args, retry: int = 3, **kwargs):
    for attempt in range(retry):
        try:
            return operation(*args, **kwargs)
        except Exception as e:
            if attempt < retry - 1:
                logger.warning(f"Operation failed, retrying... ({attempt + 1}/{retry})")
                time.sleep(2**attempt)  # Exponential backoff
            else:
                logger.error(f"Operation failed after {retry} attempts: {str(e)}")
                raise

def build_image(
    client: docker.DockerClient, build: Dict, config: Dict, cli_build_dir: str = None
):
    tag = build["tag"]
    logger.info(f"Building image: {tag}")
    build_dir = cli_build_dir or build.get("build_dir") or config.get("build_dir", ".")

    build_args = build.get("build_args", {})
    try:
        client.images.build(path=build_dir, tag=tag, buildargs=build_args)
        logger.info(f"Successfully built image: {tag}")
    except docker.errors.BuildError as e:
        logger.error(f"Build failed for {tag}: {str(e)}")
        raise

def push_image(client: docker.DockerClient, tag: str, config: Dict):
    logger.info(f"Pushing image: {tag}")
    try:
        registry_type = config["upload"]["registry_type"]
        if registry_type == "dockerhub":
            client.images.push(tag)
        elif registry_type == "ecr":
            ecr_client = boto3.client("ecr", region_name=config["region"])
            token = ecr_client.get_authorization_token()
            username, password = (
                base64.b64decode(token["authorizationData"][0]["authorizationToken"])
                .decode()
                .split(":")
            )
            registry = token["authorizationData"][0]["proxyEndpoint"]
            client.login(username=username, password=password, registry=registry)
            client.images.push(tag)
        else:
            raise ValueError(f"Unsupported registry type: {registry_type}")
        logger.info(f"Successfully pushed image: {tag}")
    except Exception as e:
        logger.error(f"Push failed for {tag}: {str(e)}")
        raise

def delete_image(client: docker.DockerClient, tag: str):
    logger.info(f"Deleting image: {tag}")
    try:
        client.images.remove(tag)
        logger.info(f"Successfully deleted image: {tag}")
    except docker.errors.ImageNotFound:
        logger.warning(f"Image not found: {tag}")
    except Exception as e:
        logger.error(f"Delete failed for {tag}: {str(e)}")
        raise

def process_image(
    client: docker.DockerClient,
    build: Dict,
    config: Dict,
    operation: Callable,
    args: argparse.Namespace,
):
    if stop_flag.is_set():
        return
    return retry_operation(
        operation, client, build, config, args.build_dir, retry=args.retry
    )

def process_images_parallel(
    client: docker.DockerClient,
    config: Dict,
    operation: Callable,
    args: argparse.Namespace,
):
    max_workers = args.parallel or config.get("max_parallel_tasks", 1)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_image, client, build, config, operation, args)
            for build in config["builds"]
        ]
        try:
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"An error occurred: {str(e)}")
                if stop_flag.is_set():
                    break
        except KeyboardInterrupt:
            logger.warning("Received interrupt, stopping operations...")
            stop_flag.set()
            executor.shutdown(wait=False)
            for future in futures:
                future.cancel()
            raise

    if (
        operation == build_image
        and config["upload"].get("auto_push", False)
        and not stop_flag.is_set()
    ):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(push_image, client, build["tag"], config)
                for build in config["builds"]
            ]
            try:
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"An error occurred while pushing: {str(e)}")
                    if stop_flag.is_set():
                        break
            except KeyboardInterrupt:
                logger.warning("Received interrupt, stopping push operations...")
                stop_flag.set()
                executor.shutdown(wait=False)
                for future in futures:
                    future.cancel()
                raise

def main():
    parser = argparse.ArgumentParser(
        description="Docker image management script for Minecraft servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  %(prog)s build\n  %(prog)s push\n  %(prog)s delete",
    )
    parser.add_argument(
        "-r",
        "--retry",
        type=int,
        default=3,
        help="Number of retries for failed operations (default: 3)",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="Path to the configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "-d", "--build-dir", help="Override the build directory for all images"
    )
    parser.add_argument(
        "--region", help="Override the region specified in the config file"
    )
    parser.add_argument(
        "--username", help="Override the username specified in the config file"
    )
    parser.add_argument(
        "--password", help="Override the password specified in the config file"
    )
    parser.add_argument(
        "-p",
        "--parallel",
        type=int,
        help="Maximum number of parallel tasks (overrides config file)",
    )

    subparsers = parser.add_subparsers(
        title="Commands", dest="command", required=True, metavar="COMMAND"
    )

    subparsers.add_parser("build", help="Build all images")
    subparsers.add_parser("push", help="Push all images")
    subparsers.add_parser("delete", help="Delete all images")

    args = parser.parse_args()

    config = load_config(args.config)

    # Override config values with command line arguments if provided
    if args.region:
        config["region"] = args.region
    if args.username:
        config["upload"]["username"] = args.username
    if args.password:
        config["upload"]["password"] = args.password

    client = docker.from_env()

    try:
        operations = {
            "build": build_image,
            "push": lambda client, build, config, cli_build_dir: push_image(
                client, build["tag"], config
            ),
            "delete": lambda client, build, _, cli_build_dir: delete_image(
                client, build["tag"]
            ),
        }
        process_images_parallel(client, config, operations[args.command], args)
    except KeyboardInterrupt:
        logger.error("Operation canceled by user")
    finally:
        client.close()

    if stop_flag.is_set():
        logger.warning("Some operations may have been interrupted")
        sys.exit(1)

if __name__ == "__main__":
    main()
