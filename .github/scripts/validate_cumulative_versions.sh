#!/bin/bash

# This script validates cumulative file versions.
# It requires `unzip` and `jq` to be installed.

# Get the root directory of the repository
REPO_ROOT=$(git rev-parse --show-toplevel)
DATA_VERSION=$(grep '__data_version__' "$REPO_ROOT/VERSION" | cut -d '"' -f 2)
BUNDLE_VERSION=$(grep '__bundle_version__' "$REPO_ROOT/VERSION" | cut -d '"' -f 2)

echo "Validating cumulative files against data version: $DATA_VERSION and bundle version: $BUNDLE_VERSION"

errors=()

# Function to check version in a zip file
check_zip_version() {
  local zip_file_path=$1
  local expected_data_version=$2
  local expected_bundle_version=$3
  if [ ! -f "$zip_file_path" ]; then
    errors+=("Cumulative file not found: $zip_file_path.")
    return
  fi

  unzip -l "$zip_file_path" | grep -q "VERSION"
  if [ $? -ne 0 ]; then
    errors+=("VERSION file not found in ${zip_file_path}.")
  else
    unzipped_content=$(unzip -p "${zip_file_path}" VERSION)
    unzipped_data_version=$(echo "$unzipped_content" | grep '__data_version__' | cut -d '"' -f 2)
    unzipped_bundle_version=$(echo "$unzipped_content" | grep '__bundle_version__' | cut -d '"' -f 2)
    if [ "$unzipped_data_version" != "$expected_data_version" ]; then
      errors+=("Data version mismatch in ${zip_file_path}. Expected ${expected_data_version}, found ${unzipped_data_version}.")
    fi
    if [ "$unzipped_bundle_version" != "$expected_bundle_version" ]; then
      errors+=("Bundle version mismatch in ${zip_file_path}. Expected ${expected_bundle_version}, found ${unzipped_bundle_version}.")
    fi
  fi
}

if find "$REPO_ROOT/texts/originals" -maxdepth 1 -type f -print -quit | grep -q .; then
    check_zip_version "$REPO_ROOT/texts/transforms/cumulative/originals_misc.zip" "$DATA_VERSION" "$BUNDLE_VERSION"
fi

if find "$REPO_ROOT/texts/processed_txt" -maxdepth 1 -type f -print -quit | grep -q .; then
    zips=(
      "texts/transforms/cumulative/txt.zip"
      "texts/transforms/cumulative/xml.zip"
      "texts/transforms/cumulative/html_plain.zip"
      "texts/transforms/cumulative/html_rich.zip"
    )
    for zip in "${zips[@]}"; do
      check_zip_version "$REPO_ROOT/$zip" "$DATA_VERSION" "$BUNDLE_VERSION"
    done
fi

# Metadata files
check_zip_version "$REPO_ROOT/metadata/transforms/cumulative/metadata_md.zip" "$DATA_VERSION" "$BUNDLE_VERSION"
check_zip_version "$REPO_ROOT/metadata/transforms/cumulative/metadata_html.zip" "$DATA_VERSION" "$BUNDLE_VERSION"

metadata_json="$REPO_ROOT/metadata/transforms/cumulative/metadata.json"
if [ ! -f "${metadata_json}" ]; then
  errors+=("metadata cumulative json file not found.")
else
  if ! command -v jq &> /dev/null
  then
      errors+=("jq could not be found, cannot check version of ${metadata_json}")
  else
    json_version=$(jq -r '.version' "${metadata_json}")
    if [ "$json_version" != "$DATA_VERSION" ]; then
      errors+=("Version mismatch in ${metadata_json}. Expected ${DATA_VERSION}, found ${json_version}.")
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

echo "All cumulative files are up to date with data version ${DATA_VERSION} and bundle version ${BUNDLE_VERSION}."