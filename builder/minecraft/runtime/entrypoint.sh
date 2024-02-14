#!/bin/bash
set -e
cd /home/container

# MCDR Debug
if ${MCDR_DEBUG}; then
    java -version
    python3 -V
    python3 /start_hook.py
fi

# Replace Startup Variables
STARTUP_CMD=$(echo "${STARTUP}" | sed -e 's/{{/${/g' -e 's/}}/}/g')
STARTUP_EXPANDED=$(echo "$STARTUP_CMD" | envsubst)
echo ":$(pwd)$ ${STARTUP_EXPANDED}"

# Run the Server
eval "${STARTUP_EXPANDED}"
