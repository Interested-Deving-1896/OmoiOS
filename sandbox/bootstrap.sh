#!/usr/bin/env bash
# OmoiOS sandbox bootstrap.
#
# Runs before OpenCode/OmO starts. Responsibilities:
#   1. If SESSION_TOKEN + BROKER_URL + OMOIOS_CREDENTIAL_ALIASES are set,
#      fetch each alias from the broker and render auth.json.
#   2. Render opencode.json and oh-my-openagent.jsonc from env templates.
#   3. Start the VNC stack (Xvfb + fluxbox + x11vnc + websockify/noVNC).
#   4. exec whatever command the caller passed (default: sleep infinity).
#
# Env contract:
#   SESSION_TOKEN                 — sess_tok_... (broker bearer)
#   BROKER_URL                    — e.g. https://api.omoios.dev/broker
#   OMOIOS_CREDENTIAL_ALIASES     — comma-separated: "anthropic,openrouter,github"
#   OMOIOS_OPENCODE_CONFIG        — JSON content for opencode.json (optional)
#   OMOIOS_OMO_CONFIG             — JSONC content for oh-my-openagent.jsonc (optional)
#   DISABLE_VNC                   — "1" to skip VNC startup

set -euo pipefail
log() { printf '[bootstrap %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

: "${HOME:?HOME must be set}"
OPENCODE_CONFIG_DIR="$HOME/.config/opencode"
OPENCODE_DATA_DIR="$HOME/.local/share/opencode"
mkdir -p "$OPENCODE_CONFIG_DIR" "$OPENCODE_DATA_DIR"
chmod 700 "$OPENCODE_DATA_DIR"

# ─── 1. auth.json from the credential broker ──────────────────────────────────
AUTH_JSON_PATH="$OPENCODE_DATA_DIR/auth.json"
if [[ -n "${SESSION_TOKEN:-}" && -n "${BROKER_URL:-}" && -n "${OMOIOS_CREDENTIAL_ALIASES:-}" ]]; then
  log "minting auth.json via broker (aliases=$OMOIOS_CREDENTIAL_ALIASES)"
  auth_json="{}"
  IFS=',' read -ra aliases <<< "$OMOIOS_CREDENTIAL_ALIASES"
  for alias in "${aliases[@]}"; do
    alias="$(echo "$alias" | tr -d '[:space:]')"
    [[ -z "$alias" ]] && continue
    if resp="$(curl -fsS \
        --max-time 10 \
        -H "Authorization: Bearer $SESSION_TOKEN" \
        "$BROKER_URL/creds/$alias" 2>/dev/null)"; then
      auth_json="$(jq --arg a "$alias" --argjson r "$resp" '. + {($a): $r}' <<< "$auth_json")"
      log "  ✓ $alias"
    else
      log "  ✗ $alias (broker returned error; skipping)"
    fi
  done
  printf '%s\n' "$auth_json" > "$AUTH_JSON_PATH"
  chmod 600 "$AUTH_JSON_PATH"
  log "wrote $AUTH_JSON_PATH (mode 0600)"
else
  log "skipping auth.json: broker env not set"
fi

# ─── 2. opencode.json + oh-my-openagent.jsonc from env templates ──────────────
if [[ -n "${OMOIOS_OPENCODE_CONFIG:-}" ]]; then
  printf '%s\n' "$OMOIOS_OPENCODE_CONFIG" > "$OPENCODE_CONFIG_DIR/opencode.json"
  log "wrote $OPENCODE_CONFIG_DIR/opencode.json"
fi
if [[ -n "${OMOIOS_OMO_CONFIG:-}" ]]; then
  printf '%s\n' "$OMOIOS_OMO_CONFIG" > "$OPENCODE_CONFIG_DIR/oh-my-openagent.jsonc"
  log "wrote $OPENCODE_CONFIG_DIR/oh-my-openagent.jsonc"
fi

# ─── 3. VNC stack ─────────────────────────────────────────────────────────────
# Uses the xvfb + x11vnc + novnc + xfce4 stack shipped in daytonaio/sandbox.
if [[ "${DISABLE_VNC:-0}" != "1" ]]; then
  export DISPLAY="${DISPLAY:-:0}"
  log "starting VNC stack on $DISPLAY (noVNC on ${NOVNC_PORT:-6080}, raw VNC on ${VNC_PORT:-5900})"
  # Xvfb: headless X server on :0.
  Xvfb "$DISPLAY" -screen 0 "${VNC_RESOLUTION:-1920x1080x24}" -nolisten tcp &
  sleep 1
  # D-Bus session bus (xfce4 needs it to register services).
  if command -v dbus-launch >/dev/null; then
    eval "$(dbus-launch --sh-syntax)" >/dev/null 2>&1 || true
  fi
  # xfce4: full desktop environment (already in the base image).
  startxfce4 >/dev/null 2>&1 &
  # x11vnc: bridges X to VNC RFB protocol.
  x11vnc -display "$DISPLAY" -forever -shared -nopw \
         -rfbport "${VNC_PORT:-5900}" -quiet >/dev/null 2>&1 &
  # noVNC: browser-accessible VNC over WebSocket.
  websockify --web=/usr/share/novnc "${NOVNC_PORT:-6080}" "localhost:${VNC_PORT:-5900}" \
    >/dev/null 2>&1 &
  log "VNC stack launched in background (xfce4 + x11vnc + noVNC)"
fi

# ─── 4. hand off ──────────────────────────────────────────────────────────────
if [[ $# -gt 0 ]]; then
  log "exec: $*"
  exec "$@"
else
  log "no command given; keeping container alive (sleep infinity)"
  exec sleep infinity
fi
