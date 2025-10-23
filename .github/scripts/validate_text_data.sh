#!/bin/bash

# Get the root directory of the repository
REPO_ROOT=$(git rev-parse --show-toplevel)

# Define paths relative to the root directory
TEXT_DATA_DIR="$REPO_ROOT/texts/processed_txt"
VALIDATION_SCRIPT="$REPO_ROOT/utils/validation/validate.py"

echo "Validation script paths:"
echo "REPO_ROOT: $REPO_ROOT"
echo "TEXT_DATA_DIR: $TEXT_DATA_DIR"
echo "VALIDATION_SCRIPT: $VALIDATION_SCRIPT"

echo "Running validation script with -s structure option"

for file in "$TEXT_DATA_DIR"/*.txt; do
    python "$VALIDATION_SCRIPT" -i "$file" -s
done

echo "Running validation script with -c content option (allow fail)"

for file in "$TEXT_DATA_DIR"/*.txt; do
    python "$VALIDATION_SCRIPT" -i "$file" -c --allow-content-fail
done

echo "Checking that generated files all exist..."
errors=()

# Check for stranded TXT files
for txt_file in "$TEXT_DATA_DIR"/*.txt; do
  xml_file="$REPO_ROOT/texts/transforms/xml/$(basename "$txt_file" .txt).xml"
  if [ ! -f "$xml_file" ]; then
    errors+=("Stranded TXT file found: $txt_file. Source .xml file does not exist. Please run 'python utils/transforms/xml/regenerate.py --xml'.")
  fi
done

# Check for stranded XML files
shopt -s nullglob
for xml_file in texts/transforms/*.xml; do
  txt_file="texts/$(basename "$xml_file" .xml).txt"
  if [ ! -f "$txt_file" ]; then
    errors+=("Stranded XML file found: $xml_file. Source .txt file does not exist. Please run 'python utils/transforms/xml/regenerate.py --txt'.")
  fi
done
shopt -u nullglob

if [ ${#errors[@]} -ne 0 ]; then
  for error in "${errors[@]}"; do
    echo "Error: $error"
  done
  exit 1
fi

echo "All text files have corresponding XML files."
