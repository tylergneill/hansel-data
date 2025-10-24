#!/bin/bash

REPO_ROOT=$(git rev-parse --show-toplevel)
SCRIPT_DIR="$REPO_ROOT/.github/scripts"

find "$SCRIPT_DIR" -type f -name "*.sh" -not -name "$(basename "$0")" | while read -r script; do
  echo "Running $script..."
  "$script"
  if [ $? -ne 0 ]; then
    echo "Error: $script failed. Aborting."
    exit 1
  fi
done

echo "All validation scripts ran successfully."
