#!/bin/bash

# This script validates cumulative file versions.
# It requires `unzip` and `jq` to be installed.

# Get the root directory of the repository
REPO_ROOT=$(git rev-parse --show-toplevel)
VERSION=$(cat "$REPO_ROOT/VERSION" | cut -d '"' -f 2)

echo "Validating cumulative files against version: $VERSION"

errors=()

# Function to check version in a zip file
check_zip_version() {
  local zip_file_path=$1
  local expected_version=$2
  if [ ! -f "$zip_file_path" ]; then
    errors+=("Cumulative file not found: $zip_file_path.")
    return
  fi

  unzip -l "$zip_file_path" | grep -q "VERSION"
  if [ $? -ne 0 ]; then
    errors+=("VERSION file not found in ${zip_file_path}.")
  else
    unzipped_version=$(unzip -p "${zip_file_path}" VERSION | cut -d '"' -f 2)
    if [ "$unzipped_version" != "$expected_version" ]; then
      errors+=("Version mismatch in ${zip_file_path}. Expected ${expected_version}, found ${unzipped_version}.")
    fi
  fi
}

if find "$REPO_ROOT/texts/originals" -maxdepth 1 -type f -print -quit | grep -q .; then
    check_zip_version "$REPO_ROOT/texts/transforms/cumulative/originals_misc.zip" "$VERSION"
fi

if find "$REPO_ROOT/texts/processed_txt" -maxdepth 1 -type f -print -quit | grep -q .; then
    zips=(
      "texts/transforms/cumulative/txt.zip"
      "texts/transforms/cumulative/xml.zip"
      "texts/transforms/cumulative/html_plain.zip"
      "texts/transforms/cumulative/html_rich.zip"
    )
    for zip in "${zips[@]}"; do
      check_zip_version "$REPO_ROOT/$zip" "$VERSION"
    done
fi

# Metadata files
check_zip_version "$REPO_ROOT/metadata/transforms/cumulative/metadata_md.zip" "$VERSION"
check_zip_version "$REPO_ROOT/metadata/transforms/cumulative/metadata_html.zip" "$VERSION"

metadata_json="$REPO_ROOT/metadata/transforms/cumulative/metadata.json"
if [ ! -f "${metadata_json}" ]; then
  errors+=("metadata cumulative json file not found.")
else
  if ! command -v jq &> /dev/null
  then
      errors+=("jq could not be found, cannot check version of ${metadata_json}")
  else
    json_version=$(jq -r '.version' "${metadata_json}")
    if [ "$json_version" != "$VERSION" ]; then
      errors+=("Version mismatch in ${metadata_json}. Expected ${VERSION}, found ${json_version}.")
    fi
  fi
fi

if [ ${#errors[@]} -ne 0 ]; then
  for error in "${errors[@]}"; do
    echo "Error: $error"
  done
  echo "Please run 'python utils/transforms/zip_texts.py' and 'python utils/transforms/metadata/regenerate.py' and commit the new files."
  exit 1
fi

echo "All cumulative files are up to date with version ${VERSION}."
