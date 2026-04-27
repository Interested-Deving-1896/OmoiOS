#!/usr/bin/env bash
# Show / switch the active Modal profile in ~/.modal.toml.
#
# Usage:
#   modal_profile.sh status            # show active + available profiles
#   modal_profile.sh switch <name>     # preview, confirm, then activate
set -euo pipefail

MODAL_TOML="${HOME}/.modal.toml"

if [ ! -f "$MODAL_TOML" ]; then
    echo "no $MODAL_TOML — run 'modal token new' first" >&2
    exit 1
fi

current_active() {
    awk '
        /^\[/   { name = substr($0, 2, length($0) - 2); next }
        /^active[[:space:]]*=[[:space:]]*true/ { print name; exit }
    ' "$MODAL_TOML"
}

list_profiles() {
    awk '/^\[/ { print substr($0, 2, length($0) - 2) }' "$MODAL_TOML"
}

status() {
    local active
    active="$(current_active)"
    echo "Modal profiles in $MODAL_TOML:"
    while IFS= read -r p; do
        if [ "$p" = "$active" ]; then
            printf "  ● %s  (active)\n" "$p"
        else
            printf "  ○ %s\n" "$p"
        fi
    done < <(list_profiles)
}

switch_profile() {
    local target="${1:?usage: switch <profile>}"
    local current
    current="$(current_active)"

    if ! list_profiles | grep -qx "$target"; then
        echo "profile '$target' not found in $MODAL_TOML" >&2
        echo "available:"
        list_profiles | sed 's/^/  - /'
        echo
        echo "add it with: modal token new --profile $target"
        exit 1
    fi

    if [ "$current" = "$target" ]; then
        echo "already on '$target' — nothing to do."
        return 0
    fi

    cat <<EOF
Modal profile switch:
  from:  ${current:-<none>}
  to:    $target

Every Modal call after this — chat_app, backend modal_spawner, poof flows,
scripts/poof/probe_sdk_modal_* — routes to the '$target' workspace until
you switch back. In-flight sandboxes stay where they are; reattach checks
the current workspace, so cross-workspace handles will look "missing" and
respawn fresh.
EOF
    read -r -p "proceed? [y/N] " reply
    case "$reply" in
        [yY]|[yY][eE][sS])
            modal profile activate "$target"
            echo "✓ active profile is now '$target'"
            ;;
        *)
            echo "aborted — no change."
            exit 0
            ;;
    esac
}

cmd="${1:-status}"
shift || true
case "$cmd" in
    status)  status ;;
    switch)  switch_profile "$@" ;;
    *)
        echo "usage: $(basename "$0") {status|switch <profile>}" >&2
        exit 2
        ;;
esac
