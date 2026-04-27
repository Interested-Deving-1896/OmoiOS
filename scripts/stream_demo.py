"""End-to-end streaming demo: API health → session bootstrap → live TUI.

One command from clean state to an interactive Textual TUI streaming the
full opencode event vocabulary (message.part.delta, session.idle,
permission.asked, file.edited, lsp.client.diagnostics, pty.*, …) into
your terminal.

What it does:

    step 0  hit GET /health on OMOIOS_API_BASE_URL  (must already be up)
    step 1  whoami — verify the API key authenticates
    step 2  workspace find-or-create (poof-life)
    step 3  fireworks credential find-or-create
    step 4  environment find-or-create (poof-kimi)
    step 5  bind env_version alias (fireworks-ai)
    step 6  session.create — fresh chat session
    step 7  exec `omoios sessions connect <SID>` — TUI takes over

Steps 0–6 reuse the existing `scripts/poof/*` probes so resource state
is shared with `just poof-*`. Step 7 hands off to the SDK CLI, which
opens the SSE + WebSocket channels and renders the new event taxonomy.

Usage:

    just stream-demo                        # one-shot, fresh session
    OMOIOS_API_BASE_URL=https://… \\
    OMOIOS_PLATFORM_API_KEY=plat_… \\
        python scripts/stream_demo.py       # explicit env override

Pre-flight failure modes:

    - API down on :18000           → asks the user to start uvicorn
    - missing API key / org id     → points at backend/.env.local
    - probe step fails             → prints PASS/FAIL line + exits non-zero

The script never starts uvicorn itself — that's a foreground process
the user owns (per project memory; uvicorn already runs in the poof
tmux session on most dev machines).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Awaitable, Callable, Optional

REPO = Path(__file__).resolve().parent.parent
for path in (REPO, REPO / "sdk" / "python", REPO / "backend"):
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts.poof import (  # noqa: E402
    api_health,
    auth_whoami,
    credential_find_or_create,
    env_version_bind_alias,
    environment_find_or_create,
    session_create,
    workspace_find_or_create,
)
from scripts.poof._client import build_client  # noqa: E402
from scripts.poof._common import (  # noqa: E402
    StepResult,
    load_merged_state,
    print_step,
    save_probe_state,
)


ProbeRun = Callable[[object, dict], Awaitable[StepResult]]


# (step_number, label, probe_module_name, run_fn, needs_client)
_BOOTSTRAP_PROBES: list[tuple[int, str, str, ProbeRun, bool]] = [
    (0, "pre-flight", api_health.PROBE_NAME, api_health.run, False),
    (1, "whoami", auth_whoami.PROBE_NAME, auth_whoami.run, True),
    (
        2,
        "workspace",
        workspace_find_or_create.PROBE_NAME,
        workspace_find_or_create.run,
        True,
    ),
    (
        3,
        "credential",
        credential_find_or_create.PROBE_NAME,
        credential_find_or_create.run,
        True,
    ),
    (
        4,
        "environment",
        environment_find_or_create.PROBE_NAME,
        environment_find_or_create.run,
        True,
    ),
    (
        5,
        "env_version",
        env_version_bind_alias.PROBE_NAME,
        env_version_bind_alias.run,
        True,
    ),
    (6, "session", session_create.PROBE_NAME, session_create.run, True),
]


def _print_banner() -> None:
    print("  ▸ stream-demo: bootstrapping a session, then launching the TUI…")


def _print_handoff(session_id: str) -> None:
    print()
    print(f"  ✓ session ready: {session_id}")
    print("  ▸ launching omoios sessions connect — Ctrl+C / Ctrl+Q to exit")
    print()


async def _bootstrap_session() -> Optional[str]:
    """Run probes 0-6 and return the freshly-minted session_id, or None.

    Side-effect: per-probe state is cached under .sisyphus/poof-state/
    so subsequent `just poof-*` runs re-use the same workspace/env.
    """
    state = load_merged_state([p[2] for p in _BOOTSTRAP_PROBES])

    # Step 0 (health) doesn't need the SDK client.
    pre = _BOOTSTRAP_PROBES[0]
    pre_result = await pre[3](None, state)
    print_step(pre[0], pre[1], pre_result)
    if pre_result.status != "PASS":
        return None

    async with build_client() as client:
        for step_num, label, _probe_name, run_fn, _needs_client in (
            _BOOTSTRAP_PROBES[1:]
        ):
            result = await run_fn(client, state)
            print_step(step_num, label, result)
            if result.status != "PASS":
                return None

    sid = state.get("session_id")
    if not isinstance(sid, str) or not sid:
        return None
    save_probe_state("stream_demo", {"session_id": sid})
    return sid


def _launch_tui(session_id: str) -> int:
    """Hand off to `omoios sessions connect <SID>`.

    Uses ``os.execvp`` so the TUI inherits our terminal directly (no
    nested Python → subprocess buffering). The poof env (OMOIOS_API_BASE_URL,
    OMOIOS_PLATFORM_API_KEY) already lives in the process env after
    `_load_env_file` was called via `get_settings`.

    Three launch paths, tried in order:

      1. ``omoios`` console script on $PATH — the happy path when the
         SDK is installed in the active venv.
      2. ``python -m omoios.cli`` — falls back to a module run when the
         binary isn't on $PATH but the package is importable.
      3. error — neither found; the user needs to install the SDK.
    """
    import shutil

    omoios_bin = shutil.which("omoios")
    if omoios_bin:
        cmd = [omoios_bin, "sessions", "connect", session_id]
    else:
        try:
            import omoios.cli  # noqa: F401
        except ImportError:
            print(
                "  ✗ omoios SDK not available — install with:\n"
                "    uv pip install --editable sdk/python\n"
                "    or run via:  uv run --with-editable sdk/python "
                "omoios sessions connect " + session_id,
                file=sys.stderr,
            )
            return 127
        cmd = [sys.executable, "-m", "omoios.cli", "sessions", "connect", session_id]

    _print_handoff(session_id)
    try:
        os.execvp(cmd[0], cmd)
    except FileNotFoundError as exc:
        print(f"  ✗ {cmd[0]} not on PATH: {exc}", file=sys.stderr)
        return 127


async def _run(launch_tui: bool) -> int:
    _print_banner()
    sid = await _bootstrap_session()
    if sid is None:
        print(
            "\n  ✗ bootstrap failed — see PASS/FAIL above.\n"
            "    common fixes:\n"
            "      • API down on :18000  → tmux attach -t poof  (window 0)\n"
            "      • missing creds        → check backend/.env.local\n"
            "      • stale state          → just stream-demo-fresh",
            file=sys.stderr,
        )
        return 1
    if not launch_tui:
        print(f"\n  ✓ session bootstrapped (--no-tui): {sid}")
        return 0
    return _launch_tui(sid)  # never returns on success — execvp replaces us


def main() -> int:
    # Tiny manual flag parser — argparse pulls in I/O latency we don't need.
    launch_tui = "--no-tui" not in sys.argv[1:]
    try:
        return asyncio.run(_run(launch_tui=launch_tui))
    except KeyboardInterrupt:
        print("\n  · interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
