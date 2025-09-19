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

echo "Checking for XML file consistency..."
errors=()

# Check for missing XML files
for txt_file in texts/tier_ii/*.txt; do
  xml_file="texts/tier_ii/transforms/$(basename "$txt_file" .txt).xml"
  if [ ! -f "$xml_file" ]; then
    errors+=("XML file for $txt_file not found. Please run 'python utils/transforms/xml/regenerate.py --xml'.")
  fi
done

# Check for stale XML files
shopt -s nullglob
for xml_file in texts/tier_ii/transforms/*.xml; do
  txt_file="texts/tier_ii/$(basename "$xml_file" .xml).txt"
  if [ ! -f "$txt_file" ]; then
    errors+=("Stale XML file found: $xml_file. Source .txt file does not exist. Please run 'python utils/transforms/xml/regenerate.py --xml'.")
  fi
done
shopt -u nullglob

if [ ${#errors[@]} -ne 0 ]; then
  for error in "${errors[@]}"; do
    echo "Error: $error"
  done
  exit 1
fi

echo "All Tier II text files have corresponding XML files and no stale XML files were found."
