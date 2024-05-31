# FoxRealms Pterodactyl Files

**Internal Repository, Do Not Distribute, Violators Will Be Prosecuted**

## Introduction

This is a place to store things related to the Pterodactyl panel.

- The `template` folder contains backup configuration files for the Pterodactyl panel, both in YAML and JSON formats. Conversion between the two can be done using the `run.sh` script located in this directory.
- The `docker` folder contains tools for building images.
> It is divided into two parts, `installer` and `runtime`, which are described as follows:
> - `installer` is used to automatically download and install the server.
> - `runtime` is the environment required to run the server (including MCDR and related dependencies).

**Please note: Only JSON versions of the configuration files can be imported. Please do not import the YAML versions directly.**

## Acknowledgements

This repository contains a lot of code references from Fallen_breath's personal repository: https://github.com/Fallen-Breath/pterodactyl-eggs

## Copyright

This repository belongs to FoxRealms and all rights are reserved.