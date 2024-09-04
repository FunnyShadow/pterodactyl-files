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

init(autoreset=True)

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

def load_config(config_file: str) -> Dict:
    with open(config_file, 'r') as file:
        return yaml.safe_load(file)

def docker_login(client: docker.DockerClient, config: Dict):
    if config['upload']['registry_type'] == 'dockerhub':
        try:
            client.login(
                username=config['upload']['username'],
                password=config['upload']['password']
            )
            print_log("SUCCESS", "Successfully logged in to Docker Hub")
        except docker.errors.APIError as e:
            print_log("ERROR", f"Failed to log in to Docker Hub: {str(e)}")
            sys.exit(1)

def retry_operation(operation: Callable, *args, retry: int = 3, **kwargs):
    for attempt in range(retry):
        try:
            return operation(*args, **kwargs)
        except docker.errors.APIError as e:
            print_log("ERROR", f"Operation failed: {str(e)}")
            if attempt < retry - 1:
                print_log("WARN", f"Retrying... (Attempt {attempt + 1} of {retry})")
                time.sleep(5)
            else:
                print_log("ERROR", "Max retries reached. Operation failed.")
                return None

def get_build_dir(global_build_dir: str, build_config: Dict, cli_build_dir: str) -> str:
    # Priority: CLI arg > individual build config > global config > current working directory
    return cli_build_dir or build_config.get('build_dir') or global_build_dir or os.getcwd()

def build_image(client: docker.DockerClient, build_config: Dict, global_config: Dict, cli_build_dir: str):
    tag = build_config['tag']
    build_args = build_config['build_args']
    build_args['REGION'] = global_config['region']
    
    build_dir = get_build_dir(global_config.get('build_dir'), build_config, cli_build_dir)

    print_log("INFO", f"Building image: {tag}")
    print_log("INFO", f"Using build directory: {build_dir}")
    image, _ = client.images.build(
        path=build_dir,
        tag=tag,
        buildargs=build_args,
        nocache=True
    )
    print_log("SUCCESS", f"Successfully built image: {tag}")
    return image

def push_image(client: docker.DockerClient, tag: str, config: Dict):
    docker_login(client, config)  # 只在推送时登录
    print_log("INFO", f"Pushing image: {tag}")
    for line in client.images.push(tag, stream=True, decode=True):
        if 'error' in line:
            raise docker.errors.APIError(line['error'])
    print_log("SUCCESS", f"Successfully pushed image: {tag}")

def delete_image(client: docker.DockerClient, tag: str):
    print_log("INFO", f"Deleting image: {tag}")
    try:
        client.images.remove(tag)
        print_log("SUCCESS", f"Successfully deleted image: {tag}")
    except docker.errors.ImageNotFound:
        print_log("WARN", f"Image not found: {tag}")

def process_images(client: docker.DockerClient, config: Dict, operation: Callable, args: argparse.Namespace):
    for build in config['builds']:
        retry_operation(operation, client, build, config, args.build_dir, retry=args.retry)
        if operation == build_image and config['upload']['auto_push']:
            retry_operation(push_image, client, build['tag'], config, retry=args.retry)

def main():
    parser = argparse.ArgumentParser(
        description="Docker image management script for Minecraft servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  %(prog)s build\n  %(prog)s push\n  %(prog)s delete"
    )
    parser.add_argument("-r", "--retry", type=int, default=3, help="Number of retries for failed operations (default: 3)")
    parser.add_argument("-c", "--config", default="config.yaml", help="Path to the configuration file (default: config.yaml)")
    parser.add_argument("-d", "--build-dir", help="Override the build directory for all images")
    parser.add_argument("--region", help="Override the region specified in the config file")
    parser.add_argument("--username", help="Override the username specified in the config file")
    parser.add_argument("--password", help="Override the password specified in the config file")
    
    subparsers = parser.add_subparsers(title="Commands", dest="command", required=True, metavar="COMMAND")

    subparsers.add_parser("build", help="Build all images")
    subparsers.add_parser("push", help="Push all images")
    subparsers.add_parser("delete", help="Delete all images")

    args = parser.parse_args()

    config = load_config(args.config)

    # Override config values with command line arguments if provided
    if args.region:
        config['region'] = args.region
    if args.username:
        config['upload']['username'] = args.username
    if args.password:
        config['upload']['password'] = args.password

    client = docker.from_env()

    try:
        operations = {
            "build": build_image,
            "push": lambda client, build, config, cli_build_dir: push_image(client, build['tag'], config),
            "delete": lambda client, build, _, cli_build_dir: delete_image(client, build['tag'])
        }
        process_images(client, config, operations[args.command], args)
    except KeyboardInterrupt:
        print_log("ERROR", "Operation canceled by user")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    main()
