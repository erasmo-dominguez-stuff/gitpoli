#!/bin/sh
set -e

TARGET="${SMEE_TARGET:-http://server:8080/webhook}"

# Auto-create smee channel if URL not provided
if [ -z "${SMEE_URL}" ] || [ "${SMEE_URL}" = "https://smee.io/YOUR_CHANNEL_ID" ]; then
  echo "SMEE_URL not set — creating new smee.io channel..."
  SMEE_URL=$(wget -q -O /dev/null -S --max-redirect=0 https://smee.io/new 2>&1 \
    | grep -i '^  Location:' | awk '{print $2}' | tr -d '\r') || true

  if [ -z "${SMEE_URL}" ]; then
    echo "ERROR: Could not auto-create smee channel."
    echo "Visit https://smee.io/new and set SMEE_URL in your .env file."
    exit 1
  fi

  echo "============================================"
  echo "  New smee channel created:"
  echo "  ${SMEE_URL}"
  echo ""
  echo "  Configure this URL as the webhook in your"
  echo "  GitHub repository settings."
  echo "============================================"
fi

echo "Forwarding ${SMEE_URL} → ${TARGET}"
exec smee --url "${SMEE_URL}" --target "${TARGET}"
