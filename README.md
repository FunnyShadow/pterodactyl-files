# TRCloud Studio Pterodactyl Resources

<div align="center">

[中文版本](README.cn.md) | [English Version](README.md)

</div>

## Introduction

This repository contains Pterodactyl panel-related resources used by TRCloud Studio

### Directory Structure

- `docker/`: Image building related tools
  - `installer/`: For automatically downloading and installing servers
  - `runtime/`: Environment required for running servers (including MCDR and related dependencies)

- `template/`: Pterodactyl panel preset configuration files
  - Includes YAML and JSON format versions
  - `convert.py`: Script for converting between YAML and JSON formats

> **Note**: Only JSON format preset configuration files are supported for import. Do not directly import YAML format files.

## Usage Instructions

1. Image Building: Use the tools in the `docker/` directory for server installation and environment configuration
2. Preset Configuration: Select the required JSON format configuration file from the `template/` directory and import it into the Pterodactyl panel
3. Format Conversion: If you need to convert YAML format to JSON, please use the `template/convert.py` script

## Acknowledgements

Most of the code in this repository is referenced from [Fallen_breath](https://github.com/Fallen-Breath)'s personal repository: [pterodactyl-eggs](https://github.com/Fallen-Breath/pterodactyl-eggs)

## License

All files in this repository are subject to the Apache 2.0 license. For detailed information, please refer to the [LICENSE](LICENSE) file
