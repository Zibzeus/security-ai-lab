from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send one signed request to BAS Executor"
    )
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    parser.add_argument("--capability", required=True)
    parser.add_argument("--case-id", default="manual-smoke-test")
    parser.add_argument("--arguments", default="{}")
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()

    shared_secret = os.environ.get("EXECUTOR_SECRET", "")
    if len(shared_secret) < 32:
        raise SystemExit("Set EXECUTOR_SECRET to the configured 32+ character secret")
    arguments = json.loads(args.arguments)
    body = json.dumps(
        {
            "capability": args.capability,
            "arguments": arguments,
            "case_id": args.case_id,
            "approved": args.approved,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    signature = hmac.new(
        shared_secret.encode(),
        timestamp.encode() + b"." + nonce.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    request = urllib.request.Request(
        f"{args.url.rstrip('/')}/v1/execute",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-BAS-Timestamp": timestamp,
            "X-BAS-Nonce": nonce,
            "X-BAS-Signature": signature,
        },
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        print(response.read().decode())


if __name__ == "__main__":
    main()
