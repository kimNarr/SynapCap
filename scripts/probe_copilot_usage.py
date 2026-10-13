"""Read Copilot account quotas without creating a chat or consuming inference.

Install github-copilot-sdk separately, or in build/provider-probe/deps.
Uses an existing gh login; never prints or persists the GitHub credential.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "build" / "provider-probe"
if (PROBE / "deps").is_dir():
    sys.path.insert(0, str(PROBE / "deps"))
os.environ.setdefault("COPILOT_CLI_EXTRACT_DIR", str(PROBE / "runtime"))


async def probe(account: str | None) -> int:
    from copilot import CopilotClient
    from copilot.generated.rpc import AccountGetQuotaRequest

    command = ["gh", "auth", "token", "--hostname", "github.com"]
    if account:
        command += ["--user", account]
    auth = subprocess.run(command, capture_output=True, text=True, timeout=10)
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
        print(json.dumps({
            "status": "ok",
            "account": account,
            "authenticated": status.isAuthenticated,
            "quotas": {key: {
                "included": value.entitlement_requests,
                "used": value.used_requests,
                "remaining_percent": value.remaining_percentage,
                "reset_at": value.reset_date,
                "unlimited": value.is_unlimited_entitlement,
            } for key, value in result.quota_snapshots.items()},
        }, ensure_ascii=True, indent=2))
        return 0
    except Exception as exc:
        # Runtime errors can contain request context; redact before displaying.
        message = str(exc).replace(token, "[REDACTED]")[:400]
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__, "message": message}))
        return 1
    finally:
        await client.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", help="Existing gh account, without switching the active account")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(probe(args.account)))
