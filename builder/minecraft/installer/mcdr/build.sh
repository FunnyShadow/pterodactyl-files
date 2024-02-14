#!/bin/bash

set -e
tag="bluefunny/pterodactyl:installer-mcdr"
docker build "$(pwd)" -t "$tag" -f "Dockerfile"
if [ "$1" == "--push" ] && [ "$1" == "-p" ]; then
  docker push "$tag"
fi
