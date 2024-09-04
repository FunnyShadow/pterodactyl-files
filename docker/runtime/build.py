import os
import yaml
import docker
import tempfile
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

class DockerImageBuilder:
    def __init__(self, dockerfile_path='Dockerfile', default_resources_path='resources', config_path='config.yaml'):
        self.dockerfile_path = dockerfile_path
        self.default_resources_path = default_resources_path
        self.config_path = config_path
        self.client = docker.from_env()
        self.config = self.load_config()

    def load_config(self):
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def prepare_build_context(self, build_config):
        temp_dir = tempfile.mkdtemp()
        shutil.copy2(self.dockerfile_path, temp_dir)
        
        # Use custom resources path if specified, otherwise use default
        resources_path = build_config.get('resources_path', self.default_resources_path)
        if os.path.exists(resources_path):
            shutil.copytree(resources_path, os.path.join(temp_dir, 'resources'))
        return temp_dir

    def build_image(self, build_config):
        context_path = self.prepare_build_context(build_config)
        try:
            image, logs = self.client.images.build(
                path=context_path,
                dockerfile=os.path.basename(self.dockerfile_path),
                tag=build_config['tag'],
                buildargs=build_config.get('build_args', {}),
                rm=True
            )
            return image.id
        finally:
            shutil.rmtree(context_path)

    def build_all(self):
        total_builds = len(self.config['builds'])
        completed_builds = 0

        with ThreadPoolExecutor(max_workers=self.config.get('max_concurrent_builds', 3)) as executor:
            futures = {executor.submit(self.build_image, build_config): build_config for build_config in self.config['builds']}
            
            with tqdm(total=total_builds, desc="Overall Progress", position=0) as pbar:
                for future in as_completed(futures):
                    build_config = futures[future]
                    try:
                        image_id = future.result()
                        tqdm.write(f"Built image {build_config['tag']} with ID: {image_id}")
                    except Exception as e:
                        tqdm.write(f"Error building image {build_config['tag']}: {str(e)}")
                    
                    completed_builds += 1
                    pbar.update(1)

        print(f"Completed {completed_builds}/{total_builds} builds.")

if __name__ == "__main__":
    builder = DockerImageBuilder()
    builder.build_all()
