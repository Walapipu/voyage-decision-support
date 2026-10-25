# Project 4 data dictionary

- `managed_vessels.csv`: four Capesize vessels with hire, performance, position, availability, and bunker ROB inputs.
- `market_vessels.csv`: eleven Capesize candidates. Hire offer is a student decision.
- `committed_cargoes.csv`: three cargo obligations with contract freight and cargo terms.
- `market_cargoes.csv`: eight market opportunities. Freight quotation is a student decision.
- `ports.csv`: public port identities, coursework draft-screening values, and the bunker pricing location used for each port. Coordinates are not distributed.
- `ballast_distances.csv`: every vessel-position to cargo-load-port pair.
- `laden_routes.csv`: the fixed load-to-discharge leg for each cargo.
- `bunker_forward_curve.csv`: monthly VLSFO and MGO coursework assumptions based on past price data. These are not current market quotations or forecasts.
- `ffa_reference.csv`: Capesize route references for market context.
- `commercial_assumptions.csv`: the complete calculation convention.
- `vessel_class_ranges.csv`: broad Capesize screening range.
- `validation_example.csv`: one recoverable arithmetic check, not an allocation answer.
- `source_register.csv`: references, uses, and limitations.

## Key joins

- Join a vessel's `current_port` and a cargo's `load_port` to `ballast_distances.csv`.
- Join `cargo_id` to `laden_routes.csv`.
- Join port codes to `ports.csv`.
- Read `bunker_pricing_location` directly from `ports.csv`, then join period, pricing location, and grade to `bunker_forward_curve.csv`.

## Units and decisions

TCE and hire rates are USD per day. Freight rates are USD per tonne. DWT, cargo, ROB, purchase, and consumption are tonnes. Speed is knots. Draft is metres. Dates and times are UTC.

Quantity tolerance is contractual flexibility. The selected lift must fall between the stated minimum and maximum and must pass deadweight and draft screening after fuel reserves and other deadweight are included.
