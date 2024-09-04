#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Change to the container's home directory
cd /home/container || exit 1

# Function to log messages
log() {
    echo "[Pterodactyl Daemon]: $*"
}

# Replace Startup Variables
STARTUP_CMD=${STARTUP//\{\{/\$\{} # Replace '{{' with '${'
STARTUP_CMD=${STARTUP_CMD//\}\}/\}} # Replace '}}' with '}'

# Expand environment variables
STARTUP_EXPANDED=$(eval echo "$STARTUP_CMD")

log "Current directory: $(pwd)"
log "Expanded startup command: $STARTUP_EXPANDED"

# Run the Server
eval "$STARTUP_EXPANDED"
