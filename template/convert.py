import argparse
import json
import sys
import os
from ruamel.yaml import YAML, RoundTripRepresenter

def repr_str(dumper: RoundTripRepresenter, s: str):
    if '\n' in s:
        return dumper.represent_scalar('tag:yaml.org,2002:str', s, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', s)

def get_parser(name: str):
    if name.endswith('.yml') or name.endswith('yaml'):
        yaml = YAML()
        yaml.width = 2 ** 20
        yaml.representer.add_representer(str, repr_str)
        return yaml
    else:
        return json

def convert_file(input_file, output_file, mode):
    with open(input_file, encoding='utf8') as f:
        try:
            data = get_parser(input_file).load(f)
        except ValueError as e:
            print(f'Failed to load {input_file}: {e}', file=sys.stderr)
            return

    output_ext = '.yml' if mode == 'j2y' else '.json'
    if output_file is None:
        output_file = os.path.splitext(input_file)[0] + output_ext

    with open(output_file, 'w', encoding='utf8') as f:
        kwargs = {'indent': 4} if mode == 'y2j' else {}
        get_parser(output_file).dump(data, f, **kwargs)

def convert_directory(directory, mode):
    for root, _, files in os.walk(directory):
        for file in files:
            input_file = os.path.join(root, file)
            if mode == 'y2j' and file.endswith('.yml') or file.endswith('.yaml'):
                convert_file(input_file, None, mode)
            elif mode == 'j2y' and file.endswith('.json'):
                convert_file(input_file, None, mode)

def main():
    parser = argparse.ArgumentParser(description='egg builder tools')

    parser.add_argument('-m', '--mode', choices=['y2j', 'j2y'], required=True, help='Conversion mode (y2j: YAML to JSON, j2y: JSON to YAML)')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-d', '--directory', help='Directory to convert files')
    group.add_argument('-f', '--file', help='Single file to convert')

    args = parser.parse_args()

    if args.directory:
        convert_directory(args.directory, args.mode)
    else:
        convert_file(args.file, None, args.mode)

if __name__ == '__main__':
    main()