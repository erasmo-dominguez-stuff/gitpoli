#!/usr/bin/env bash
set -euo pipefail

# Handler registry tests for extensibility
BASE_URL="${BASE_URL:-http://localhost:8080}"
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

PASS=0
FAIL=0

printf "\n=== Handler Registry Extensibility ===\n"

# Test: registry returns handler for pull_request
curl -sf -X POST "$BASE_URL/webhook" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -d '{"action": "opened", "pull_request": {"head": {"ref": "feature/test", "sha": "abc123"}, "base": {"ref": "main"}, "number": 1}, "repository": {"full_name": "test/repo"}}' > /dev/null && {
  echo -e "${GREEN}PASS${NC} (pull_request handler dispatched)"; PASS=$((PASS+1));
} || {
  echo -e "${RED}FAIL${NC} (pull_request handler not dispatched)"; FAIL=$((FAIL+1));
}

# Test: registry returns handler for deployment_protection_rule
curl -sf -X POST "$BASE_URL/webhook" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: deployment_protection_rule" \
  -d '{"deployment": {"ref": "main", "environment": "production"}, "deployment_callback_url": "http://example.com/callback", "installation": {"id": 1}}' > /dev/null && {
  echo -e "${GREEN}PASS${NC} (deploy handler dispatched)"; PASS=$((PASS+1));
} || {
  echo -e "${RED}FAIL${NC} (deploy handler not dispatched)"; FAIL=$((FAIL+1));
}

# Test: registry returns ignored for unknown event
curl -sf -X POST "$BASE_URL/webhook" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: unknown_event" \
  -d '{}' | grep '"action": "ignored"' > /dev/null && {
  echo -e "${GREEN}PASS${NC} (unknown event ignored)"; PASS=$((PASS+1));
} || {
  echo -e "${RED}FAIL${NC} (unknown event not ignored)"; FAIL=$((FAIL+1));
}

printf "\nResults: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}\n"
[ "$FAIL" -eq 0 ] || exit 1
