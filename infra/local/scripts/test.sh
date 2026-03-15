#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOADS_DIR="${SCRIPT_DIR}/../payloads"
BASE_URL="${BASE_URL:-http://localhost:8080}"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

PASS=0
FAIL=0

# ── Wait for server ──────────────────────────────────────────────────────────

echo "Waiting for policy server at ${BASE_URL}..."
for i in $(seq 1 30); do
  if curl -sf "${BASE_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}Server ready${NC}"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo -e "${RED}Server not ready after 30s${NC}"
    exit 1
  fi
  sleep 1
done

# ── Test runner ──────────────────────────────────────────────────────────────

run_test() {
  local name="$1"
  local endpoint="$2"
  local payload="$3"
  local expect_allow="$4"

  printf "  %-50s " "${name}"
  RESULT=$(curl -sf -X POST "${BASE_URL}${endpoint}" \
    -H "Content-Type: application/json" \
    -d "@${payload}" 2>&1) || {
    echo -e "${RED}FAIL (curl error)${NC}"
    FAIL=$((FAIL + 1))
    return
  }

  ALLOW=$(echo "$RESULT" | jq -r '.allow')
  if [ "$ALLOW" = "$expect_allow" ]; then
    echo -e "${GREEN}PASS${NC} (allow=${ALLOW})"
    PASS=$((PASS + 1))
  else
    echo -e "${RED}FAIL${NC} (expected=${expect_allow} got=${ALLOW})"
    echo "    violations: $(echo "$RESULT" | jq -c '.violations')"
    FAIL=$((FAIL + 1))
  fi
}

# ── Pull Request Policy ─────────────────────────────────────────────────────

echo ""
echo "=== Pull Request Policy ==="

run_test "Valid PR (feature/login -> develop)" \
  "/evaluate/pullrequest" \
  "${PAYLOADS_DIR}/pr_valid.json" \
  "true"

run_test "Denied PR (branch naming violation)" \
  "/evaluate/pullrequest" \
  "${PAYLOADS_DIR}/pr_denied.json" \
  "false"

# ── Deploy Policy ───────────────────────────────────────────────────────────

echo ""
echo "=== Deploy Policy ==="

run_test "Valid deploy (production, main)" \
  "/evaluate/deploy" \
  "${PAYLOADS_DIR}/deploy_valid.json" \
  "true"

run_test "Denied deploy (wrong branch)" \
  "/evaluate/deploy" \
  "${PAYLOADS_DIR}/deploy_denied.json" \
  "false"

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo "=== Audit Trail ==="

AUDIT_COUNT=$(curl -sf "${BASE_URL}/audit?limit=10" | jq '. | length')
if [ "$AUDIT_COUNT" -ge 4 ]; then
  echo -e "  ${GREEN}${AUDIT_COUNT} audit events recorded${NC}"
  PASS=$((PASS + 1))
else
  echo -e "  ${RED}Expected >= 4 audit events, got ${AUDIT_COUNT}${NC}"
  FAIL=$((FAIL + 1))
fi

echo ""
echo "────────────────────────────────────────────────────"
echo -e "Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}"
[ "$FAIL" -eq 0 ] || exit 1
