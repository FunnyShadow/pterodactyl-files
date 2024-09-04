import os
import yaml
import docker
import tempfile
import shutil
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

class DockerImageBuilder:
    REGISTRY_PRESETS = {
        'dockerhub': '',
        'ghcr': 'ghcr.io',
        'acr': 'azurecr.io',
        'ecr': 'amazonaws.com',
        'gcr': 'gcr.io',
    }

    def __init__(self, dockerfile_path='Dockerfile', config_path='config.yaml'):
        self.dockerfile_path = dockerfile_path
        self.config_path = config_path
        self.client = docker.from_env()
        self.config = self.load_config()
        self.default_resources_path = self.config.get('default_resources_path', 'resources')
        self.region = self.config.get('region', 'global')
        self.upload_config = self.config.get('upload', {})

    def load_config(self):
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def prepare_build_context(self, build_config):
        temp_dir = tempfile.mkdtemp()
        shutil.copy2(self.dockerfile_path, temp_dir)
        
        resources_path = build_config.get('resources_path', self.default_resources_path)
        if os.path.exists(resources_path):
            shutil.copytree(resources_path, os.path.join(temp_dir, 'resources'))
        return temp_dir

    def build_image(self, build_config):
        context_path = self.prepare_build_context(build_config)
        try:
            build_args = build_config.get('build_args', {})
            build_args['REGION'] = build_config.get('region', self.region)

            image, logs = self.client.images.build(
                path=context_path,
                dockerfile=os.path.basename(self.dockerfile_path),
                tag=build_config['tag'],
                buildargs=build_args,
                rm=True
            )
            return image
        finally:
            shutil.rmtree(context_path)

    def get_registry_url(self):
        registry_type = self.upload_config.get('registry_type', 'custom').lower()
        if registry_type == 'custom':
            return self.upload_config.get('registry', '')
        elif registry_type in self.REGISTRY_PRESETS:
            return self.REGISTRY_PRESETS[registry_type]
        else:
            tqdm.write(f"Unknown registry type: {registry_type}. Using custom registry.")
            return self.upload_config.get('registry', '')

    def upload_image(self, image, build_config):
        if not self.upload_config.get('enabled', False):
            return

        registry_url = self.get_registry_url()
        username = self.upload_config.get('username')
        password = self.upload_config.get('password')

        if username and password:
            self.client.login(username=username, password=password, registry=registry_url)
            
            if registry_url:
                tag = f"{registry_url}/{build_config['tag']}"
            else:
                tag = build_config['tag']  # For Docker Hub
            
            image.tag(tag)
            push_logs = self.client.images.push(tag)
            tqdm.write(f"Uploaded image {tag}")
        else:
            tqdm.write("Upload configuration is incomplete. Skipping upload.")

    def build_and_upload(self, build_config):
        try:
            image = self.build_image(build_config)
            tqdm.write(f"Built image {build_config['tag']} with ID: {image.id}")
            self.upload_image(image, build_config)
            return image.id
        except Exception as e:
            tqdm.write(f"Error building/uploading image {build_config['tag']}: {str(e)}")
            return None

    def build_all(self):
        total_builds = len(self.config['builds'])
        completed_builds = 0

        with ThreadPoolExecutor(max_workers=self.config.get('max_concurrent_builds', 3)) as executor:
            futures = {executor.submit(self.build_and_upload, build_config): build_config for build_config in self.config['builds']}
            
            with tqdm(total=total_builds, desc="Overall Progress", position=0) as pbar:
                for future in as_completed(futures):
                    build_config = futures[future]
                    future.result()  # This will raise any exceptions that occurred
                    completed_builds += 1
                    pbar.update(1)

        print(f"Completed {completed_builds}/{total_builds} builds.")

def parse_arguments():
    parser = argparse.ArgumentParser(description="Docker Image Builder and Uploader")
    parser.add_argument("-c", "--config", default="config.yaml", help="Path to the configuration file (default: config.yaml)")
    parser.add_argument("-d", "--dockerfile", default="Dockerfile", help="Path to the Dockerfile (default: Dockerfile)")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without actually building or uploading images")
    parser.add_argument("--no-upload", action="store_true", help="Build images but do not upload them")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--max-concurrent", type=int, help="Maximum number of concurrent builds (overrides config file)")
    parser.add_argument("--list-presets", action="store_true", help="List available registry presets")
    return parser.parse_args()

def main():
    args = parse_arguments()

    if args.list_presets:
        print("Available registry presets:")
        for preset in DockerImageBuilder.REGISTRY_PRESETS:
            print(f"  - {preset}")
        return

    builder = DockerImageBuilder(dockerfile_path=args.dockerfile, config_path=args.config)

    if args.verbose:
        print(f"Using configuration file: {args.config}")
        print(f"Using Dockerfile: {args.dockerfile}")

    if args.dry_run:
        print("Performing dry run:")
        for build_config in builder.config['builds']:
            print(f"  Would build: {build_config['tag']}")
        return

    if args.no_upload:
        builder.upload_config['enabled'] = False
        print("Upload disabled. Images will be built but not uploaded.")

    if args.max_concurrent:
        builder.config['max_concurrent_builds'] = args.max_concurrent

    builder.build_all()

if __name__ == "__main__":
    main()