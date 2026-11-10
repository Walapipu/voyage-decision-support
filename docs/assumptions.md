# Modelling assumptions

The default follows the 2 November 2026 clarifications in the Project 3 brief. Active assumptions are exported with the results and shown in Settings.

- **Fuel plan.** Buy the minimum by grade at the current port before ballast departure and at the loading port on arrival. Maintain 300 t VLSFO and 25 t MGO through discharge and retain surplus fuel. The plan adds no time, fees or diversion. The opening-fuel ledger is a separate diagnostic without replenishment.
- **Pricing.** Value fuel consumed at the loading port's assigned regional price proxy in the cargo's laycan opening month. The month selector can run an alternate price scenario. The physical purchase ports and the regional pricing proxy are separate.
- **Timing.** Arrival at or before laycan closing UTC qualifies. Start turn time after the later of arrival and laycan opening, then load. Loading can finish after laycan closes.
- **Draft.** Add selected lift, all VLSFO and MGO on board at laden departure, and 3,000 t other deadweight. Apply the resulting departure draft to the vessel's summer limit and both port limits. Each requires 0.30 m headroom by default.
- **Economics.** TCE divides voyage cashflow before hire by voyage days. Contribution deducts voyage hire. Canal cost is provisionally zero.
- **Ranking.** Analytics and the assistant can compare one committed cargo by contribution, TCE or stressed contribution. The lift search uses a 1,000 t grid and includes nominal lift, endpoints and the freight threshold when applicable. It also adds each vessel's largest loadable lift, rounded down to the nearest 100 t. The Overview plan uses the same search, so both reach the same cargo size. Default stress uses 20% higher bunker prices, 15% higher port charges and three extra idle days at loading. Load-port delay fuel is consumed before laden departure.

CHECK-01 reconciles to 320.829 t VLSFO before ballast and 528.422 t VLSFO plus 19.817 t MGO at loading. Its corrected departure deadweight is 167,868.949 t, with 13,371.051 t deadweight margin, 17.384 m sailing draft and 0.716 m draft margin. These four figures supersede the corresponding values in the frozen validation CSV. Fuel consumption, total purchases, timing and economics are unchanged.

Edit `config/modelling.toml` and restart the app to run a diagnostic policy. For example, `opening_rob_only` excludes voyages that need replenishment, and `report_only` displays the port-draft result without applying it as an exclusion.
