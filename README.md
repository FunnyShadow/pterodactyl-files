# FoxRealms Pterodactyl Files

## Introduction

This is where FoxRealms keeps some Pterodactyl panel-related stuff.

- The `docker` folder contains tools for image building.

> It is divided into two parts, `installer` and `runtime`, which are described as follows:
> - `installer` is used to automatically download and install the server.
> - `runtime` is the environment required to run the server (including MCDR and related dependencies).

- The `template` folder contains backup files of preset configuration files for the Pterodactyl panel, both in YAML and JSON formats. Conversion between the two can be done using `run.sh` located in this directory.

**Please note: Only JSON versions of the preset configuration files can be imported. Please do not directly import the YAML versions.**

## Acknowledgements

This repository heavily references the personal repository of [Fallen_breath](https://github.com/Fallen-Breath): https://github.com/Fallen-Breath/pterodactyl-eggs

## Copyright

All files in this repository are licensed under the Apache 2.0 license. Please refer to the [LICENSE](LICENSE) file for more information.