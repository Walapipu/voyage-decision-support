# Voyage Decision Support

Step 1: connect Python to OpenRouter. The voyage engine and Streamlit interface will be added later.

## Run in VS Code (Windows)

Requires Python 3.11 or newer. This first step uses only Python's standard library.

1. Open this project folder in VS Code.
2. Create the local Python environment, if it does not already exist:

   ```powershell
   python -m venv .venv
   ```

3. Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` if missing.
4. Paste your existing OpenRouter API key between the quotes for `OPENROUTER_API_KEY` and save.
5. In the VS Code terminal, verify authentication:

   ```powershell
   .\.venv\Scripts\python.exe check_openrouter.py
   ```

6. Send one small test message to a free model:

   ```powershell
   .\.venv\Scripts\python.exe check_openrouter.py --chat
   ```

Alternatively, use **Terminal > Run Task** and select the matching task.

The first command only checks authentication. The second consumes a free inference request. Free models may be rate limited or unavailable. `openrouter/free` is suitable for this connection check; select and evaluate a specific tool-capable model later for the voyage assistant.

## Secrets

- `.streamlit/secrets.toml` is ignored by Git. Only the blank example belongs in the repository.
- Never paste the key into a chat message or commit it.
- `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` environment variables can override the local file.
- Future Streamlit deployment can use the same settings in Community Cloud Secrets.

## Next milestones

1. Validate the frozen CSV inputs and reference voyage.
2. Build the calculation, recommendation and scenario modules.
3. Add the Streamlit dashboard and connect the model to validated Python tools.

## API references

- https://openrouter.ai/docs/quickstart
- https://openrouter.ai/docs/api_reference/authentication
- https://openrouter.ai/docs/guides/routing/routers/free-router
