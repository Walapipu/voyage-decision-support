"""Check authentication and optionally send one free-model request."""
import argparse
import sys
from voyage.openrouter import load_settings, api_request

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
