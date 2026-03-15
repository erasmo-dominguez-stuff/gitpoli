#!/usr/bin/env bash
# validate_schema.sh
# Validates YAML policy configs (.repol/*.yaml) against JSON Schemas.
# Converts YAML → JSON via yq or python, then validates with check-jsonschema or jq.
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
REPOL_DIR="$ROOT/.repol"
SCHEMAS_DIR="$ROOT/schemas"

# Map: YAML policy config → JSON Schema
declare -A PAIRS=(
  ["deploy.yaml"]="github_env_protect_schema.json"
  ["pullrequest.yaml"]="github_pull_request_schema.json"
)

# ── Detect YAML→JSON converter ──────────────────────────────────────────────
yaml_to_json() {
  local yaml_file="$1"
  if command -v yq &>/dev/null; then
    yq -o=json "$yaml_file"
  elif command -v python3 &>/dev/null; then
    python3 -c "
import sys, json, yaml
with open(sys.argv[1]) as f:
    json.dump(yaml.safe_load(f), sys.stdout)
" "$yaml_file"
  else
    echo ""
    return 1
  fi
}

if ! command -v jq &>/dev/null; then
  echo -e "${RED}Error: jq is required. Install: brew install jq${NC}"
  exit 1
fi

# Check for a YAML converter
HAS_CONVERTER=false
if command -v yq &>/dev/null; then
  HAS_CONVERTER=true
elif python3 -c "import yaml" 2>/dev/null; then
  HAS_CONVERTER=true
fi

if ! $HAS_CONVERTER; then
  echo -e "${RED}Error: yq or python3 with PyYAML is required to convert YAML configs.${NC}"
  echo "Install one of:"
  echo "  brew install yq"
  echo "  pip install pyyaml"
  exit 1
fi

USE_JSONSCHEMA=false
if command -v check-jsonschema &>/dev/null; then
  USE_JSONSCHEMA=true
fi

PASS=0
FAIL=0
SKIP=0

for POLICY_FILE in "${!PAIRS[@]}"; do
  SCHEMA_FILE="${PAIRS[$POLICY_FILE]}"
  POLICY_PATH="$REPOL_DIR/$POLICY_FILE"
  SCHEMA_PATH="$SCHEMAS_DIR/$SCHEMA_FILE"

  if [ ! -f "$POLICY_PATH" ]; then
    echo -e "${YELLOW}⚠  SKIP: $POLICY_FILE not found in .repol/${NC}"
    (( SKIP++ )) || true
    continue
  fi

  if [ ! -f "$SCHEMA_PATH" ]; then
    echo -e "${YELLOW}⚠  SKIP: schema $SCHEMA_FILE not found${NC}"
    (( SKIP++ )) || true
    continue
  fi

  # Convert YAML to JSON
  TMP_JSON=$(mktemp)
  # shellcheck disable=SC2064
  trap "rm -f '$TMP_JSON'" EXIT

  if ! yaml_to_json "$POLICY_PATH" > "$TMP_JSON" 2>/dev/null; then
    echo -e "${RED}❌ FAIL (invalid YAML): $POLICY_FILE${NC}"
    (( FAIL++ )) || true
    continue
  fi

  # Verify it's valid JSON
  if ! jq empty "$TMP_JSON" &>/dev/null; then
    echo -e "${RED}❌ FAIL (YAML→JSON conversion failed): $POLICY_FILE${NC}"
    (( FAIL++ )) || true
    continue
  fi

  if $USE_JSONSCHEMA; then
    if check-jsonschema --schemafile "$SCHEMA_PATH" "$TMP_JSON" &>/dev/null; then
      echo -e "${GREEN}✅ PASS: $POLICY_FILE${NC}"
      (( PASS++ )) || true
    else
      echo -e "${RED}❌ FAIL: $POLICY_FILE does not validate against $SCHEMA_FILE${NC}"
      check-jsonschema --schemafile "$SCHEMA_PATH" "$TMP_JSON" || true
      (( FAIL++ )) || true
    fi
  else
    # Structural check: confirm top-level "policy" key with "version" field
    if jq -e '.policy.version' "$TMP_JSON" &>/dev/null; then
      echo -e "${GREEN}✅ PASS (syntax + structure): $POLICY_FILE${NC}"
      (( PASS++ )) || true
    else
      echo -e "${RED}❌ FAIL (missing .policy.version): $POLICY_FILE${NC}"
      (( FAIL++ )) || true
    fi
  fi
done

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed, ${SKIP} skipped"

if [ "$FAIL" -gt 0 ]; then
  echo -e "${RED}Schema validation failed.${NC}"
  exit 1
fi

echo -e "${GREEN}All schema validations passed.${NC}"
