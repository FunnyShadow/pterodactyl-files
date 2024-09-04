import os
import yaml
import docker
import tempfile
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

class DockerImageBuilder:
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

    def upload_image(self, image, build_config):
        if not self.upload_config.get('enabled', False):
            return

        registry = self.upload_config.get('registry')
        username = self.upload_config.get('username')
        password = self.upload_config.get('password')

        if registry and username and password:
            self.client.login(username=username, password=password, registry=registry)
            tag = f"{registry}/{build_config['tag']}"
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

if __name__ == "__main__":
    builder = DockerImageBuilder()
    builder.build_all()