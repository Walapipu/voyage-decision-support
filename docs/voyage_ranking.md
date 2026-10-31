# Cargo voyage ranking

Select a committed cargo and open **Voyages**. Rankings refresh for the cargo and bunker pricing month, using managed vessels at economical speed.

Cargo selection and pricing-month changes start an optimal quantity search and populate the recommended vessel and quantity together (CC-02 defaults to 170,600 tonnes). In this mode, changing the search step also updates the recommendation. Use a vessel card's selection button to apply that vessel's best quantity. If nothing is feasible in the optimal search, the nominal quantity is shown for inspection without a recommendation.

Editing the top tonnes field switches to **selected quantity** mode: every vessel is evaluated at exactly that amount, including quantities between search grid points. For example, entering 160,500 tonnes for CC-02 ranks feasible vessels by their profit at 160,500 tonnes. Manual quantities persist through navigation and stress changes. The search-step control is disabled in this mode. **Find optimal quantity** returns to the quantity search and restores the recommended vessel and lift.

An out-of-range quantity displays an error beside the workspace controls with the entered amount and the cargo's inclusive minimum and maximum (CC-02: 147,600–180,400 tonnes). It is excluded for every vessel and cannot produce a ranking recommendation. Quantities within this range must still pass laycan, deadweight and draft checks. Downloads identify the quantity mode and selected tonnes in their assumptions.

The Cargo ranking tab uses cards rather than a spreadsheet. Selected voyage details contains route, feasibility, economics and timeline information for the top controls. Assumptions, grouped exclusion reasons and downloads can be expanded when needed.

Adapted from `rank_any_cargo_with_tonnes.py`, the search includes minimum, nominal, maximum, the special freight threshold when in range, and a quantity grid (default 1,000 tonnes). This is a grid search, not a continuous optimum. Each vessel's best feasible configuration is ranked by baseline contribution after hire, breaking ties by TCE and vessel ID. All quantity, laycan, deadweight and minimum draft checks must pass. If no configuration passes, no recommendation is made.

Stress defaults to 20% higher bunker prices, three extra idle port days, 15% higher port costs, and zero additional ballast. Added idle days consume fuel and incur hire. Extra ballast changes arrival and may miss laycan; this is flagged. A stress scenario is not a probability or forecast. The blended score uses `(1 - weight) * baseline + weight * stress`; its rank spans all feasible baseline configurations and does not replace the baseline-profit recommendation.

Voyage horizons differ. This is not a fleet allocation optimiser. Existing engine conventions, including provisional zero canal cost, apply. JSON downloads include assumptions, all feasible options and exclusions; CSV downloads contain the best configuration for each feasible vessel. The feature does not write output files on the server.
