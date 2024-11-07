import argparse
import json
import os
from ruamel.yaml import YAML


def get_parser(name: str):
    if name.lower().endswith((".yml", ".yaml")):
        yaml = YAML()
        yaml.width = 2**20
        return yaml
    return json


def convert_file(input_file: str, output_dir: str, mode: str):
    output_ext = ".yml" if mode == "j2y" else ".json"
    if output_dir:
        output_file = os.path.join(
            output_dir, os.path.basename(os.path.splitext(input_file)[0]) + output_ext
        )
    else:
        output_file = os.path.splitext(input_file)[0] + output_ext

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    try:
        with open(input_file, encoding="utf8") as f:
            data = get_parser(input_file).load(f)

        with open(output_file, "w", encoding="utf8") as f:
            kwargs = {"indent": 4} if mode == "y2j" else {}
            get_parser(output_file).dump(data, f, **kwargs)
    except Exception as e:
        print(f"Conversion failed {input_file}: {e}")


def convert_directory(input_dir: str, output_dir: str, mode: str):
    for root, _, files in os.walk(input_dir):
        for file in files:
            if (mode == "y2j" and file.lower().endswith((".yml", ".yaml"))) or (
                mode == "j2y" and file.lower().endswith(".json")
            ):

                input_file = os.path.join(root, file)
                if output_dir:
                    rel_path = os.path.relpath(root, input_dir)
                    current_output_dir = os.path.join(output_dir, rel_path)
                else:
                    current_output_dir = root

                convert_file(input_file, current_output_dir, mode)


def main():
    parser = argparse.ArgumentParser(description="YAML and JSON converter")
    parser.add_argument(
        "-m",
        "--mode",
        choices=["y2j", "j2y"],
        required=True,
        help="Conversion mode (y2j: YAML to JSON, j2y: JSON to YAML)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-d", "--directory", help="Directory to convert")
    group.add_argument("-f", "--file", help="Single file to convert")
    parser.add_argument("-o", "--output", help="Output directory")

    args = parser.parse_args()

    if args.directory:
        convert_directory(args.directory, args.output, args.mode)
    else:
        convert_file(args.file, args.output, args.mode)


if __name__ == "__main__":
    main()
