#!/usr/bin/env python3
"""Output the original Home Assistant integration's setup fields without a proxy.

Python 3.12+, standard library only. Default: offline generation.
Use --login to make one login request and include a session token.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

# Permit running this script directly from a checkout, without installing HA.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.yuno_energy.yuno_api.auth import (  # noqa: E402
    BASE_URL,
    AuthConfig,
)


class NoRedirect(HTTPRedirectHandler):
    """Never forward account credentials to a redirected destination."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def fetch_session_token(auth: AuthConfig) -> str:
    """Make one login request with exactly the bytes covered by the signature."""
    if auth.login_body is None:
        raise ValueError("A generated login body is required")
    request = Request(
        BASE_URL + "/api/login",
        data=auth.login_body.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": auth.basic_authorization,
            "X-Http-originid": auth.origin_id,
            "X-Http-signature": auth.login_signature,
        },
        method="POST",
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as err:
        raise ValueError(f"Yuno rejected login (HTTP {err.code}); no retry attempted") from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("Could not reach Yuno; no retry attempted") from None
    except (ValueError, UnicodeError):
        raise ValueError("Yuno returned an invalid response; no retry attempted") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("sessionToken"), str):
        raise ValueError("Yuno returned no session token; no retry attempted")
    token = payload["sessionToken"]
    if not token:
        raise ValueError("Yuno returned no session token; no retry attempted")
    return str(token)


def main() -> int:
    """Prompt for credentials and output only the required setup fields."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--login", action="store_true", help="sign in once and include a session token"
    )
    parser.add_argument(
        "--output", type=Path, help="write a new, owner-only JSON file instead of stdout"
    )
    args = parser.parse_args()
    if args.output and os.path.lexists(args.output):
        parser.error("output file already exists; choose a new filename")
    email = os.environ.get("YUNO_EMAIL")
    password = os.environ.get("YUNO_PASSWORD")
    if (email is None or password is None) and not sys.stdin.isatty():
        parser.error("run in a terminal, or set YUNO_EMAIL and YUNO_PASSWORD")
    if email is None:
        print("Yuno email: ", end="", file=sys.stderr, flush=True)
        email = input()
    if password is None:
        password = getpass.getpass("Yuno password: ")
    try:
        auth = AuthConfig.from_account_credentials(email, password)
        values = auth.setup_values()
        if args.login:
            values["session_token"] = fetch_session_token(auth)
        output = json.dumps(values, indent=2) + "\n"
        if args.output:
            fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as handle:
                handle.write(output)
            print(f"Saved setup values to {args.output}", file=sys.stderr)
        else:
            print(output, end="")
    except (ValueError, OSError) as err:
        print(str(err), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
