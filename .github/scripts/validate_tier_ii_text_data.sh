#!/bin/bash

# Get the root directory of the repository
REPO_ROOT=$(git rev-parse --show-toplevel)

# Define paths relative to the root directory
TEXT_DATA_DIR="$REPO_ROOT/texts/tier_ii"
VALIDATION_SCRIPT="$REPO_ROOT/utils/validation/validate.py"

echo "validation script paths:"
echo "REPO_ROOT: $REPO_ROOT"
echo "TEXT_DATA_DIR: $TEXT_DATA_DIR"
echo "VALIDATION_SCRIPT: $VALIDATION_SCRIPT"

echo "running validation script with -s structure option"

for file in "$TEXT_DATA_DIR"/*.txt; do
    python "$VALIDATION_SCRIPT" -i "$file" -s
done

echo "running validation script with -c content option (allow fail for Tier II)"

for file in "$TEXT_DATA_DIR"/*.txt; do
    python "$VALIDATION_SCRIPT" -i "$file" -c --allow-content-fail
done
