# Voyage Decision Support

Streamlit chat and calculator for the frozen Capesize case. OpenRouter interprets a question, Python tools calculate the voyage, and a second model call explains it. Charts read Python results directly.

The OceanFlow dashboard follows the supplied reference with a fleet panel, assistant, interactive port map, freight table and estimated timeline. Dark mode is on by default; use the moon button at the far right of the top bar for light mode. Select a vessel, committed cargo, lift and pricing month to update the calculated panels together. Navigation opens source tables, voyage economics, analytics, exports and documentation. Search filters vessel/cargo lists and source-data pages. The name dropdown opens session profile settings and local logout. Desktop panel contents scroll independently so the composer stays visible. See [asset credits](docs/asset_credits.md) for licensed ship photos, Lucide icons and the Leaflet/OpenStreetMap map. Map tiles require internet; photos are stored locally.

See [metric coverage](docs/metric_coverage.md) for the reference-to-project audit. Unsupported live operational KPIs are marked unavailable. TCE, contribution, cost drivers and commercial constraints are added explicitly. Required scenario analysis and switching thresholds remain pending and are flagged in the app.

See [the architecture and Mermaid diagram](docs/architecture.md) for the four layers, assumptions and current boundaries.

## Run locally in VS Code

Requires Python 3.11+ (developed with 3.12).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` only if missing. Add your key locally. Do not overwrite a saved key or commit it. `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` environment variables can override the file.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Open http://localhost:8501 or use **Terminal > Run Task > Start Streamlit chatbot**. The Voyage calculator needs no API calls. Example chat: **Compare the managed vessels for CC-02 at 164,000 tonnes.**

## Verify

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe check_openrouter.py
.\.venv\Scripts\python.exe check_openrouter.py --chat
```

Tests mock model replies and do not use API quota. The connection check authenticates; `--chat` sends one real free-model request. A tool-based chat uses up to two requests. Free providers can be rate limited or unavailable; failed requests may consume quota too.

## Scope

The catalog contains 15 vessels and 11 cargoes. Calculations currently cover four managed vessels and three committed cargoes at a specified lift. Python checks quantity, laycan, draft and deadweight, and returns TCE before hire and contribution after hire. Source files are preserved in `data/raw/`. The single supplied validation row is regression tested; MF-02's comparison is derived, not a second official reference.

Market quote inputs, market calculations, sensitivities and fleet allocation optimisation are not yet implemented. See the architecture notes for provisional draft, pricing-month and canal conventions. No live prices replace frozen data.

## Secrets and deployment

The local secrets file, virtual environment and logs are ignored by Git. Only the blank example is committed. API calls run server-side. Chat and requested tool results are sent to OpenRouter/model providers.

Future Streamlit Community Cloud deployment can use this repository, branch `main`, entry point `app.py`, and Cloud Secrets. The app is currently local, not publicly deployed.
