#!/bin/bash

set -e
for systems in "debian" "alpine"; do
  tag="bluefunny/pterodactyl:general-runtime-${systems}"

  docker build "$(pwd)" -t "$tag" -f "Dockerfile-${systems}"
  if [ "$1" == "--push" ] && [ "$1" == "-p" ]; then
    docker push "$tag"
  fi
done
