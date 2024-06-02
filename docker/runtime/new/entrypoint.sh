#!/bin/bash
set -e
cd /workspace

if [ "${STARTUP_CMD}" == "" ]; then
    java -jar minecraft_server.jar --nogui
else
    STARTUP_EXPANDED=$(echo "$STARTUP_CMD" | envsubst)
    eval "${STARTUP_EXPANDED}"
fi