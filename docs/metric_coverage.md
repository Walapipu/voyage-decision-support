# Reference dashboard versus Project 3 requirements

Source: Project_3_Freight-Decision-Support-Tool.pdf, pages 1–4 (core scope, key questions, MVP and success criteria), checked against the supplied OceanFlow reference image.

## Reference metrics

| Reference item | What this app can truthfully show |
|---|---|
| Active voyages | Unavailable: the source has availability dates but no activity history or actual voyage records. |
| Fleet utilisation | Unavailable: no occupied-day history or agreed measurement horizon. |
| Fuel cost | Selected voyage's calculated bunker expense, in USD; consumed fuel is separately shown in tonnes. No mock-up fuel numbers or trend percentages. |
| ETA reliability | Unavailable: no actual-versus-planned arrival history. Estimated arrival dates are deterministic calculations, not reliability probabilities. |
| Profit margin | Selected voyage contribution after hire divided by freight revenue. Explicitly scoped to that voyage, not the portfolio. Infeasible selections are labelled hypothetical. |
| Fleet overview | All 4 managed and 11 market vessel records, DWT, current port and availability date. No fabricated names, photographs or live “On voyage”/maintenance statuses. |
| Route, distance, fuel, duration, ETA | Source port names and ballast/laden distances, engine fuel/duration, derived discharge arrival and completion dates. |
| Route map | Detailed zoomable Leaflet/OpenStreetMap basemap. Approximate external port-vicinity coordinates are separately sourced in data/map_locations.json; dashed connectors are schematic. Navigable routes, weather and congestion feeds remain unavailable. |
| Freight planning | Committed/market cargoes, routes, nominal lift and contract rates. Market rates are “Quote needed”; booked/completed statuses are unavailable. |
| Timeline | Calculated availability, load arrival, loading start, load departure, discharge arrival and completion, all in UTC. Not actual completed/in-progress statuses. |
| Percentage trends | Omitted: no historical comparison series. |

The five reference KPI slots are retained. Unsupported operational metrics are shown as unavailable rather than silently replaced with different metrics.

## Required project metrics absent or insufficient in the image

| Metric or capability | Implementation status |
|---|---|
| TCE and contribution after hire, compared across alternatives | Visible in the centre summary and managed-vessel comparison. |
| Revenue, commission, port costs, fuel costs, hire and total costs | Available in the economics expander and Voyages page. Canal cost remains explicitly provisional zero. |
| Bunker consumption versus purchase requirement | Both displayed, split into VLSFO and MGO. Opening ROB affects purchases, not consumption expense. |
| Ballast/waiting/loading/laden/discharge duration and consistent attribution | Engine breakdown shown in Voyages; total time and route-leg distances are visible in the dashboard. |
| Laycan slack and pass/fail checks | Visible. Negative slack is infeasible; no “optimal route” claim. |
| Selected lift versus permitted range, DWT and draft restrictions | Lift range, estimated draft and draft headroom shown; full deadweight/quantity checks in engine output. All four constraints feed feasibility. |
| Transparent pricing month, speed and TCE conventions | Visible selection controls, source results, Settings, methodology export. |
| Market vessel/cargo comparison and missing commercial inputs | Hire offers and freight quotes are stated assumptions derived from the pack's FFA references; see Market rate assumptions. |
| Bunker-price and port-delay sensitivity | Analytics and chat can rank by stressed contribution using a defined bunker-price, port-charge and load-port delay case. |
| Threshold where a recommendation switches | Pending. |
| Fleet allocation/employment recommendation | Overview plan allocates the four owned vessels across committed and market cargoes and charters in market vessels where that covers a committed cargo more profitably. The Alternatives panel prices dropping each pairing, swapping two owned vessels and every other use of a focused vessel or cargo. |
| Export results | Comparison CSV and methodology downloads available in Reports. |

Break-even or target-TCE freight estimates, interactive sliders and portfolio optimisation algorithms are optional extensions in the brief. They should not displace the required scenario/threshold work.

## Interpretation limits

The default uses economical speeds, the loading-port regional price proxy and the cargo laycan opening month. The 0.30 m draft margin applies to summer draft and both port limits. Two-stop replenishment maintains reserves through discharge. Late arrivals are excluded with reasons. See the assumption log and `config/modelling.toml` for active policy. Canal cost remains provisionally zero. Contribution comparisons span different durations; no common-horizon fleet optimum is claimed.
