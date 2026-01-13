#!/bin/bash
# ModelVault Docker Helper Script
# This script simplifies running ModelVault commands with Docker

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}Warning: docker-compose not found, using 'docker compose' instead${NC}"
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Function to build the image
build() {
    echo -e "${GREEN}Building ModelVault Docker image...${NC}"
    $COMPOSE_CMD build
    echo -e "${GREEN}✓ Build complete${NC}"
}

# Function to run modelvault command
run_command() {
    $COMPOSE_CMD run --rm modelvault "$@"
}

# Function to open shell
shell() {
    echo -e "${GREEN}Opening interactive shell in ModelVault container...${NC}"
    $COMPOSE_CMD run --rm modelvault-shell
}

# Function to show usage
usage() {
    cat << EOF
${GREEN}ModelVault Docker Helper Script${NC}

Usage:
  $0 <command> [arguments]

Commands:
  ${YELLOW}build${NC}                    Build the ModelVault Docker image
  ${YELLOW}shell${NC}                    Open an interactive bash shell in container
  ${YELLOW}store${NC} <path> <name>      Store a model artifact
  ${YELLOW}load${NC} <hash> <path>       Load a model artifact
  ${YELLOW}list${NC}                     List all stored models
  ${YELLOW}rollback${NC} <hash> <name>   Rollback to a previous version
  ${YELLOW}help${NC}                     Show ModelVault help

Examples:
  $0 build
  $0 store ./models/my_model.pkl my_model
  $0 list
  $0 load abc123def ./models/restored.pkl
  $0 load latest ./models/latest.pkl --model-name my_model
  $0 rollback abc123def my_model
  $0 shell

Notes:
  - Ensure .modelvaultrc is configured in your project root
  - AWS/GCP credentials should be configured (see DOCKER.md)
  - Run this script from your project root directory

EOF
}

# Main script logic
if [ $# -eq 0 ]; then
    usage
    exit 0
fi

case "$1" in
    build)
        build
        ;;
    shell)
        shell
        ;;
    store|load|list|rollback|help)
        run_command "$@"
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        usage
        exit 1
        ;;
esac
