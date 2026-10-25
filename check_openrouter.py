"""Check OpenRouter authentication; optionally send one free-model request.

Python 3.11+ standard library only. No key or raw API errors are logged.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import tomllib
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SECRETS = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
BASE_URL = "https://openrouter.ai/api/v1"


def load_settings():
    settings = {}
    if SECRETS.exists():
        try:
            with SECRETS.open("rb") as handle:
                settings = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError):
            raise ValueError("Cannot read secrets.toml. Keep the key inside double quotes.") from None
    key = os.environ.get("OPENROUTER_API_KEY") or settings.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("OPENROUTER_MODEL") or settings.get("OPENROUTER_MODEL", "openrouter/free")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Add OPENROUTER_API_KEY to .streamlit/secrets.toml and save it first.")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("OPENROUTER_MODEL must be a model name.")
    return key.strip(), model.strip()


def api_request(path, key, payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        BASE_URL + path,
        data=body,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "User-Agent": "VoyageDecisionSupport/0.1",
        },
        method="POST" if payload is not None else "GET",
    )
    try:
        with urlopen(request, timeout=45) as response:
            return json.load(response)
    except HTTPError as exc:
        messages = {
            401: "OpenRouter rejected the API key. Check that the complete key was pasted.",
            402: "OpenRouter reports insufficient credits or a billing restriction.",
            403: "OpenRouter denied access. Check the key permissions or account restrictions.",
            404: "The requested API endpoint or model is unavailable.",
            429: "The free API quota or provider capacity limit was reached. Try later.",
        }
        raise ValueError(messages.get(exc.code, f"OpenRouter returned HTTP {exc.code}. Try later.")) from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("Could not reach OpenRouter. Check your internet connection and try again.") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("OpenRouter returned an unreadable response.") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chat", action="store_true", help="Also send one short free-model test request.")
    args = parser.parse_args()
    try:
        key, model = load_settings()
        account = api_request("/key", key)
        if not isinstance(account, dict) or not isinstance(account.get("data"), dict):
            raise ValueError("OpenRouter did not return a valid authentication response.")
        print("OpenRouter authentication succeeded. Your key was not printed.")
        if not args.chat:
            print("To test a model reply, run this script again with --chat.")
            return 0
        if model != "openrouter/free" and not model.endswith(":free"):
            raise ValueError("This starter only permits openrouter/free or a model ending in :free.")
        result = api_request("/chat/completions", key, {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with one short sentence confirming that this API connection works."}],
            "max_tokens": 1024,
            "stream": False,
            "provider": {"max_price": {"prompt": 0, "completion": 0}},
        })
        try:
            reply = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ValueError("No model reply was returned. Retry later or choose another free model.") from None
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("The model returned no text. Retry later or choose another free model.")
        print("Model reply:", reply.strip().replace(key, "[redacted]"))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
