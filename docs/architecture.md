# Voyage assistant architecture

Four logical layers run in one Python/Streamlit application. OpenRouter is the external model API. There is no local LLM, separate frontend build, vector database or embedding step.

```mermaid
flowchart TD
    User[User in browser] --> UI["1. Streamlit interface: chat or calculator"]
    UI --> Chat["2. Chat orchestration: messages and tool schemas"]
    Chat --> Interpret["OpenRouter call 1: interpret and request tools"]
    Interpret --> Validate["Python dispatcher: validate allowed operation and inputs"]
    Validate --> Decision["3. Decision logic: compare and check feasibility"]
    Decision --> Engine["Decimal Python engine: time, fuel, draft, TCE, contribution"]
    Data["4. Data layer: frozen CSVs, joins, assumptions"] --> Engine
    Engine --> Results["Structured results: numbers, failed checks, conventions"]
    Results --> Explain["OpenRouter call 2: explain returned results"]
    Explain --> UI
    Results --> Charts["Streamlit tables and charts from engine data"]
    Charts --> UI
    UI -->|Calculator bypasses AI| Decision
```

| Layer | Files | Responsibility |
|---|---|---|
| Interface | `app.py`, `voyage/dashboard.py`, `voyage/dashboard_data.py`, `voyage/dashboard.css`, `voyage/chat_view.py`, `voyage/ui.py` | Dashboard, dark/light themes, selection controls, chat, tables, charts and exports |
| Interaction | `voyage/chat.py`, `voyage/tools.py`, `voyage/openrouter.py` | Prompt, model calls, schema validation, allowlisted tools |
| Decision and calculation | `voyage/decision.py`, `voyage/engine.py` | Feasibility, comparison, Decimal calculations, structured output |
| Data | `voyage/data.py`, `data/raw/` | Read-only records, unique keys, required joins, baseline price coverage |

Decision and calculation are separate modules within layer 3. This preserves the brief's calculation, decision and interaction responsibilities. Module boundaries support future expansion without needing additional servers now.

## Example request

User asks: “Compare managed vessels for CC-02 at 164,000 tonnes.” The first model call requests `compare_vessels` with the cargo and lift. Python validates the arguments and calculates four voyages. The second model call explains the returned results. Streamlit renders those same results into tables and charts. No model-generated code executes.

General terminology questions may use one model call without tools. Calculations use at most two model calls and four tool requests. If the explanation fails, computed evidence is still displayed. No automatic API retries consume quota. Dashboard selections and voyage calculations work without a key. The chat receives the current UI selection as context and must still call Python tools for numeric answers.

## Implemented scope

- Catalog of all 15 vessels and 11 cargoes.
- Calculations for four managed vessels and three committed cargoes at an explicit lift and month.
- Quantity, laycan, deadweight and draft checks; infeasible results omitted from comparison charts.
- TCE, contribution, duration and detailed results. Comparisons order feasible voyages by contribution; no fleet-level optimum claim.
- Regression against the single supplied validation row, including 25 numeric fields at published precision.
- Server-side key and free-only routing with zero maximum prompt/completion prices.

## Conventions requiring team agreement

- Economical speeds; ballast, waiting, loading, laden and discharge time all included.
- Default bunker month explicitly March 2026, at the load-port pricing location. The reference does not distinguish arrival-month from availability-month pricing.
- Draft margin 0.3 m below the minimum summer/load-port/discharge-port limit. This generalisation requires sign-off.
- Canal cost provisionally zero because route canal costs are absent.
- Fuel expense uses consumption times price; opening ROB affects purchase planning.
- TCE excludes hire; contribution deducts voyage hire. Different durations mean this is not a common-horizon fleet optimum.
- Original source README/dictionary use Project 4 while the brief says Project 3; originals are preserved.

## Next additions

Market quote inputs and calculations; explicit delay and bunker scenarios; allocation objectives and common-horizon comparisons; Streamlit Community Cloud deployment. Optimisation and slider controls can follow the basic scenarios. These are not implemented yet.

The free router may select different models/providers per call. Evaluate and pin a free tool-capable model before demonstration. Native tool support is requested; unavailable providers produce a visible error. A model can still omit tools or answer inaccurately, so numeric evidence is displayed separately and AI prose requires review. This is not a guarantee against hallucinations.

## Hosting and secrets

VS Code runs Streamlit locally; GitHub stores code and synthetic inputs; OpenRouter runs the model remotely. Later, Streamlit Community Cloud can run this same app with its Secrets settings. The key stays on the server, outside browser configuration and tool results.

Chat messages and requested tool results go to OpenRouter/model providers. Session history stays in server memory, not a database. Only ten recent exchanges plus the new question are sent. Follow-up calculations must rerun tools; prior AI prose is not authoritative evidence.

## References

- [OpenRouter tool calls](https://openrouter.ai/docs/guides/features/tool-calling)
- [Streamlit chat input](https://docs.streamlit.io/develop/api-reference/chat/st.chat_input)
- [Streamlit chat messages](https://docs.streamlit.io/develop/api-reference/chat/st.chat_message)

## Presentation assets and local profile

Lucide SVG icons and representative, attributed bulk-carrier photos are bundled locally. Leaflet loads OpenStreetMap tiles over the internet; separately sourced approximate port coordinates only drive the display. Frozen route distances still drive Python economics. The name dropdown edits a session profile; local logout clears session state, without account authentication or changing server credentials. Desktop dashboard and assistant panels retain a visible composer while their contents scroll.

## Analyst replies and visual reports

The `Generate analyst review` action requires a `compare_vessels` tool call. Ordinary questions retain automatic tool selection. The engine returns full-precision voyage rows; `analysis.py` prepares margins, cost shares, ballast shares and differences with Pandas/NumPy. These deterministic facts travel with the tool response to the model. The model writes a short commercial briefing covering conclusion, cost drivers, constraints and next action.

The same result object is rendered inside the assistant message as a Plotly dashboard: earnings comparison, revenue-to-contribution waterfall and stacked voyage durations, plus a comparison table and calculation details. Model text is never parsed as chart data and generated Python/JavaScript is never executed. Each chat response has separate chart keys, so repeated calculations remain independent. Reports remain visible when the explanation API fails after successful calculation. If no voyage is feasible, no vessel is labelled a recommendation and the earnings-ranking chart is replaced with an explicit status.

The valuation engine still uses Decimal. Pandas/NumPy handle presentation analytics; Plotly draws interactive figures. SciPy is not needed for these descriptive charts; numerical optimisation remains future work.

## Financial colours and layout

Positive margin/contribution is green, negative is red, and break-even is amber. The margin gradient uses a fixed, symmetric display range of -25% to +25%, saturating outside it. This is a visual scale, not a claim about industry benchmarks. Missing margins remain neutral. The application shell fits the viewport without page scrolling. Chat, fleet, freight and secondary-page content have their own overflow areas. Desktop and tablet widths retain the three-column dashboard, and smaller widths use a bounded two-row grid. The timeline remains inside the window. Search, month, selection and chat controls share a 36px height; panel gaps are 8px. Native sidebar controls remain visible and release the sidebar width when collapsed. Vessel-name buttons select managed vessels; market-vessel names open a details dialog. The map follows the selected theme and refits on container resize.

### Commentary boundary

A live provider test fabricated a savings figure despite grounding instructions. Calculated replies therefore use a stricter second-call contract: the model returns four short, qualitative JSON fields without numeric claims or IDs. Python formats all financial statements, margins, differences, constraint measurements and identifiers directly from the engine. Invalid or unavailable commentary falls back to the same calculated briefing with a visible notice. This validates structure and keeps displayed quantitative statements deterministic; qualitative model commentary still needs human review and is not guaranteed semantically correct.
