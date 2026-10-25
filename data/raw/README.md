# Project 4: Capesize Voyage Recommendation and Freight Decision Support Data Pack

## What this pack represents

The pack contains four managed Capesize vessels, eleven market Capesize vessels, three committed cargoes, eight market cargoes, public port identities, rounded route distances, fuel-price curves, and Capesize freight-market references. It supports a portfolio-allocation exercise, not live fixtures or company economics.

These are modeled coursework records, not observations of company operations. They do not reproduce vessel identities, counterparties, contracts, prices, or decisions.

The bunker forward curves are coursework assumptions based on past price data. They are not current market quotations or forecasts.

## Start here

Explore the managed and market vessel portfolios alongside the committed and market cargoes. Consider availability, position, laycan, quantity, vessel capacity, draft, and commercial status when deciding which combinations warrant further analysis.

Use the route, port, fuel-price, and commercial-assumption files to work out how a feasible voyage should be evaluated. Develop and document your own method for comparing possible allocations. Use `validation_example.csv` as a reasonableness check, not as an allocation recommendation or prescribed solution.

## Key commercial meanings

TCE is freight revenue less commission, bunker, port, and canal costs, divided by voyage days. Vessel hire is excluded from TCE. Voyage contribution deducts vessel hire from voyage cashflow.

A managed vessel uses its supplied hire rate. A market vessel requires a student-stated hire offer. A committed cargo uses its supplied freight rate. A market cargo requires a student-stated freight quotation. The selected cargo lift must stay within its quantity tolerance and pass deadweight and draft screening.

The vessel DWT screening range is 170,000–210,000 tonnes, and the nominal cargo screening range is 145,000–195,000 tonnes. Contractual quantity tolerances may extend beyond the nominal range, so feasibility must use each cargo's stated tolerance together with the selected vessel's DWT and draft constraints.

The calculation includes ballast and laden sailing, laycan waiting, cargo operations, VLSFO and MGO consumption, opening ROB, fuel reserves, port costs, commission, and hire. Route and draft values are coursework screening inputs. They are suitable for comparing alternatives, not for navigation, fixing, or operational approval.

The pack supplies base data only and does not prescribe sensitivity increments. Students may define their own delay and bunker-price changes when testing sensitivity.
