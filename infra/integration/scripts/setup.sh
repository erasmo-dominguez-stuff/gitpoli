#!/usr/bin/env bash
set -euo pipefail
#
# Sets up the integration environment:
# 1. Creates a smee.io channel (or reuses SMEE_URL from .env)
# 2. Validates GitHub App credentials are set
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

# ── GitHub App credentials ───────────────────────────────────────────────────

ERRORS=0

if [ -z "${GITHUB_APP_ID:-}" ]; then
  echo ""
  echo -e "${RED}GITHUB_APP_ID not set in .env${NC}"
  echo "Set the App ID from your GitHub App → General → App ID"
  ERRORS=1
fi

PEM_FILE="${GITHUB_APP_PRIVATE_KEY_FILE:-./app.pem}"
# Resolve relative to the .env dir
if [[ "$PEM_FILE" != /* ]]; then
  PEM_FILE="${SCRIPT_DIR}/../${PEM_FILE}"
fi

if [ ! -f "$PEM_FILE" ]; then
  echo ""
  echo -e "${RED}Private key not found: ${PEM_FILE}${NC}"
  echo "Download the .pem file from your GitHub App → General → Private keys"
  echo "Place it at: infra/integration/app.pem"
  ERRORS=1
else
  echo -e "${GREEN}Private key found: ${PEM_FILE}${NC}"
fi

if [ "$ERRORS" -ne 0 ]; then
  echo ""
  echo -e "${RED}Fix the errors above, then re-run: make integration-setup${NC}"
  echo ""
fi

# ── Instructions ─────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}═══ Integration Setup ═══${NC}"
echo ""
echo -e "  ${BOLD}1.${NC} Set GITHUB_APP_ID and place app.pem in ${SCRIPT_DIR}/.."
echo ""
echo -e "  ${BOLD}2.${NC} Install your GitHub App on the target repository:"
echo "     → https://github.com/settings/apps → Install App → Select repo"
echo ""
echo -e "  ${BOLD}3.${NC} Add a webhook (or let the App deliver events):"
echo "     → Settings → Webhooks → Add webhook"
echo -e "     Payload URL:  ${CYAN}${SMEE_URL}${NC}"
echo "     Content type: application/json"
echo "     Events:       ☑ Deployment protection rules"
echo ""
echo -e "  ${BOLD}4.${NC} Enable the custom deployment protection rule:"
echo "     → Settings → Environments → (select env) → Deployment protection rules"
echo "     → Enable your webhook-based rule"
echo ""
echo -e "  ${BOLD}5.${NC} Start the integration stack:"
echo -e "     ${CYAN}make integration-up${NC}"
echo ""
echo -e "  ${BOLD}6.${NC} Trigger a deployment and watch the audit trail:"
echo -e "     ${CYAN}curl -s http://localhost:8080/audit | jq .${NC}"
echo ""
echo -e "${BOLD}═══════════════════════${NC}"
