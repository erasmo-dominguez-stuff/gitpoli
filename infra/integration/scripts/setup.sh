#!/usr/bin/env bash
set -euo pipefail
#
# Sets up the integration environment:
# 1. Creates a smee.io channel (or reuses SMEE_URL from .env)
# 2. Validates GITHUB_TOKEN is set
# 3. Prints instructions for configuring the GitHub repo
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Load or create .env ─────────────────────────────────────────────────────

if [ ! -f "$ENV_FILE" ]; then
  echo -e "${CYAN}Creating .env from template...${NC}"
  cp "${SCRIPT_DIR}/../.env.example" "$ENV_FILE"
fi

# shellcheck source=/dev/null
source "$ENV_FILE" 2>/dev/null || true

# ── Smee channel ─────────────────────────────────────────────────────────────

if [ -z "${SMEE_URL:-}" ] || [ "$SMEE_URL" = "https://smee.io/YOUR_CHANNEL_ID" ]; then
  echo -e "${CYAN}Creating new smee.io channel...${NC}"

  if command -v npx &>/dev/null; then
    SMEE_URL=$(npx --yes smee --new 2>/dev/null || true)
  fi

  if [ -z "${SMEE_URL:-}" ]; then
    # Fallback: curl the smee redirect
    SMEE_URL=$(curl -sfL -o /dev/null -w '%{url_effective}' https://smee.io/new 2>/dev/null || true)
  fi

  if [ -z "${SMEE_URL:-}" ]; then
    echo -e "${RED}Could not create smee channel. Visit https://smee.io/new and set SMEE_URL in .env${NC}"
    exit 1
  fi

  sed -i.bak "s|SMEE_URL=.*|SMEE_URL=${SMEE_URL}|" "$ENV_FILE" && rm -f "${ENV_FILE}.bak"
  echo -e "${GREEN}Smee channel: ${SMEE_URL}${NC}"
else
  echo -e "${GREEN}Using existing smee channel: ${SMEE_URL}${NC}"
fi

# ── GitHub token ─────────────────────────────────────────────────────────────

if [ -z "${GITHUB_TOKEN:-}" ] || [ "$GITHUB_TOKEN" = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" ]; then
  echo ""
  echo -e "${RED}GITHUB_TOKEN not set in .env${NC}"
  echo "Create a token at: https://github.com/settings/tokens"
  echo "Required scope: repo (classic) or actions:write (fine-grained)"
  echo "Then edit: ${ENV_FILE}"
  echo ""
fi

# ── Instructions ─────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}═══ Integration Setup ═══${NC}"
echo ""
echo -e "  ${BOLD}1.${NC} Set GITHUB_TOKEN in ${ENV_FILE}"
echo ""
echo -e "  ${BOLD}2.${NC} Add a webhook to your GitHub repo:"
echo "     → Settings → Webhooks → Add webhook"
echo -e "     Payload URL:  ${CYAN}${SMEE_URL}${NC}"
echo "     Content type: application/json"
echo "     Events:       ☑ Deployment protection rules"
echo ""
echo -e "  ${BOLD}3.${NC} Enable the custom deployment protection rule:"
echo "     → Settings → Environments → (select env) → Deployment protection rules"
echo "     → Enable your webhook-based rule"
echo ""
echo -e "  ${BOLD}4.${NC} Start the integration stack:"
echo -e "     ${CYAN}make integration-up${NC}"
echo ""
echo -e "  ${BOLD}5.${NC} Trigger a deployment (push to main, or use workflow_dispatch)"
echo "     and watch the audit trail:"
echo -e "     ${CYAN}curl -s http://localhost:8080/audit | jq .${NC}"
echo ""
echo -e "${BOLD}═══════════════════════${NC}"
