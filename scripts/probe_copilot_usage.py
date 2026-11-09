"""Read Copilot account quotas without creating a chat or consuming inference.

Uses an existing gh login; never prints or persists the GitHub credential.
The release build packages this module as a standalone helper process.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path


def _probe_state_dir() -> Path:
    home = Path.home()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", home / ".local" / "state"))
    state_dir = base / "SynapCap" / "copilot"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


PROBE = _probe_state_dir()
os.environ.setdefault("COPILOT_CLI_EXTRACT_DIR", str(PROBE / "runtime"))


async def probe(account: str | None) -> int:
    try:
        from copilot import CopilotClient
        from copilot.generated.rpc import AccountGetQuotaRequest
    except ImportError:
        print(json.dumps({"status": "dependency_missing"}))
        return 2

    command = ["gh", "auth", "token", "--hostname", "github.com"]
    if account:
        command += ["--user", account]
    try:
        auth = await asyncio.to_thread(
            subprocess.run,
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError:
        print(json.dumps({"status": "gh_not_installed"}))
        return 2
    token = auth.stdout.strip()
    if auth.returncode or not token:
        print(json.dumps({"status": "github_login_required"}))
        return 1
    client = CopilotClient(
        github_token=token,
        use_logged_in_user=False,
        working_directory=str(PROBE),
        base_directory=str(PROBE / "state"),
        log_level="error",
    )
    try:
        await asyncio.wait_for(client.start(), timeout=45)
        status = await asyncio.wait_for(client.get_auth_status(), timeout=20)
        result = await client.rpc.account.get_quota(AccountGetQuotaRequest(), timeout=25)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "account": account,
                    "authenticated": status.isAuthenticated,
                    "quotas": {
                        key: {
                            "included": value.entitlement_requests,
                            "used": value.used_requests,
                            "remaining_percent": value.remaining_percentage,
                            "reset_at": value.reset_date,
                            "unlimited": value.is_unlimited_entitlement,
                        }
                        for key, value in result.quota_snapshots.items()
                    },
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - SDK failures must become safe JSON
        # Runtime errors can contain request context; redact before displaying.
        message = str(exc).replace(token, "[REDACTED]")[:400]
        print(
            json.dumps({"status": "failed", "error_type": type(exc).__name__, "message": message})
        )
        return 1
    finally:
        await client.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--account", help="Existing gh account, without switching the active account"
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Validate bundled dependencies without reading a GitHub account",
    )
    args = parser.parse_args()
    if args.self_check:
        try:
            import copilot  # noqa: F401
            from copilot.generated import rpc  # noqa: F401
        except ImportError:
            print(json.dumps({"status": "dependency_missing"}))
            raise SystemExit(2) from None
        print(json.dumps({"status": "ready"}))
        raise SystemExit(0)
    raise SystemExit(asyncio.run(probe(args.account)))
