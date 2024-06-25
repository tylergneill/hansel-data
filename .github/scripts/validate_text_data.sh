#!/bin/bash

# Get the root directory of the repository
REPO_ROOT=$(git rev-parse --show-toplevel)

# Define paths relative to the root directory
TEXT_DATA_DIR="$REPO_ROOT/text_data"
VALIDATION_SCRIPT="$REPO_ROOT/validation/validate.py"

echo "validation script paths:"
echo "REPO_ROOT: $REPO_ROOT"
echo "TEXT_DATA_DIR: $TEXT_DATA_DIR"
echo "VALIDATION_SCRIPT: $VALIDATION_SCRIPT"

echo "running validation script with -s structure option"

for file in "$TEXT_DATA_DIR"/*.txt; do
    python "$VALIDATION_SCRIPT" -i "$file" -s
done

echo "running validation script with -c content option"

for file in "$TEXT_DATA_DIR"/*.txt; do
    python "$VALIDATION_SCRIPT" -i "$file" -c
done
