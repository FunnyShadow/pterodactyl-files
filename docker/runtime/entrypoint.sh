#!/bin/bash
set -eo pipefail

# Configuration
CONTAINER_DIR="/home/container"
LOG_PREFIX="[Pterodactyl]"

# Utility functions
log() { echo "${LOG_PREFIX} \$1"; }
info() { log "[INFO] \$1"; }
warn() { log "[WARN] \$1" >&2; }
error() { log "[ERROR] \$1" >&2; exit 1; }

# Environment setup
setup_environment() {
    cd "${CONTAINER_DIR}" || error "Failed to change to container directory"
    info "Current working directory: $(pwd)"
}

# Startup command preparation
prepare_startup_cmd() {
    [ -z "${STARTUP}" ] && error "STARTUP environment variable is not set."
    STARTUP_CMD=$(echo "${STARTUP}" | sed -e 's/{{/${/g' -e 's/}}/}/g')
    STARTUP_EXPANDED=$(echo "$STARTUP_CMD" | envsubst)
    info "Startup command: ${STARTUP_EXPANDED}"
}

# Version checks
check_versions() {
    local cmds=("java" "python" "node")
    for cmd in "${cmds[@]}"; do
        if command -v "$cmd" &> /dev/null; then
            version=$($cmd --version 2>&1 | head -n 1)
            info "${cmd^} version: $version"
        fi
    done
}

# Security checks
perform_security_checks() {
    if [ "$(id -u)" = "0" ]; then
        warn "Container is running as root. This is not recommended."
    fi
}

# Main execution
main() {
    setup_environment
    prepare_startup_cmd
    check_versions
    perform_security_checks

    info "Starting the server..."
    eval "${STARTUP_EXPANDED}" || error "Failed to start the server."
}

# Run the script
main "$@"
