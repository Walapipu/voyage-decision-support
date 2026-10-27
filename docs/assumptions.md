# Modelling assumptions

## Laycan: late combinations are excluded

For this project, a vessel–cargo combination that misses laycan is excluded from recommendations outright. A profitable late voyage cannot override this check. No extension, renegotiation or late-arrival penalty is assumed. Failed combinations remain visible for diagnosis, with hypothetical economics.

The current timing test uses **arrival at the loading port at or before the supplied closing timestamp (UTC)**. Arrival exactly at closing passes. An early arrival waits until laycan opens; waiting time and its fuel consumption are included. Loading need not finish before closing under this simplified test.

**Provisional assumption:** arrival is used as a proxy for readiness. The inputs do not define a contractual Notice of Readiness (NOR) milestone, inspections, customs clearance or readiness delays. Confirm the required milestone with the teaching team; a readiness requirement could exclude more combinations.

This is a modelling choice, not a claim that contracts cancel automatically. The [laycan guide](https://tidesignalnews.com/laycan-shipping/) explains that the contractual readiness/NOR conditions govern and that late arrival can give the charterer an option to cancel. [BIMCO's Cancelling Clause 2002](https://www.bimco.org/contractual-affairs/bimco-clauses/current-clauses/cancelling_clause_2002/) specifically uses readiness to load and gives charterers a cancellation option; it is a reference, not an identified contract for these cargoes.

## Fuel availability: no implicit replenishment

The engine starts with the vessel's opening remaining-on-board (ROB) inventory. VLSFO and MGO are tracked **separately** through ballast passage, waiting, loading, laden passage and discharge. Each stage uses the supplied consumption rates. Port MGO consumption is zero under the supplied formulas.

Closing inventory = opening inventory − stage consumption. With nonnegative, constant consumption within a stage and no delivery, checking the closing balance also detects exhaustion during that stage. The engine records the first shortage and its estimated elapsed voyage time for each fuel grade. Negative balances are unmet demand in a hypothetical projection, not permission to continue sailing.

**No fuel deliveries are currently scheduled.** The supplied purchase quantities are total requirements, not evidence of a delivery before a particular leg. A pricing reference such as SGSIN is not a bunkering instruction. If opening fuel cannot cover every stage, the result is **replenishment plan required**, and is excluded from recommendations until an explicit replenishment plan can be modelled and validated. This is not a claim that replenishment is impossible.

For CHECK-01, MF-01 opens with 438 t VLSFO but consumes about 458.829 t during ballast. It lacks **20.829 t before reaching the loading port**, even without enforcing a reserve. A purchase at the loading port cannot remedy that earlier shortfall.

The audit checks against zero inventory. Whether the 300 t VLSFO / 25 t MGO reserves must be maintained continuously or only at a specified milestone remains unresolved. Reserves continue to enter purchase requirements and the confirmed departure-deadweight formula. Passing the zero-inventory audit does not establish reserve compliance.

## Arithmetic versus an executable voyage

CHECK-01 is an arithmetic reference, not proof of operational feasibility. Its 25 numerical reference values remain unchanged. Bunker expense is consumed fuel × reference price; fuel purchases are consumption + reserves − opening ROB, floored at zero. They are not added a second time to voyage expenses.

Departure deadweight = selected lift + laden-leg VLSFO and MGO + 300 t VLSFO reserve + 25 t MGO reserve + 3,000 t other deadweight.

Estimated sailing draft = ballast draft + (summer draft − ballast draft) × departure deadweight / vessel DWT.

The current draft check provisionally requires 0.30 m below the minimum of summer, loading-port and discharge-port limits. The teaching clarification confirms the summer-draft margin calculation; it does not settle the scope of port margins or a current-port check. A future replenishment plan must also reconcile fuel carried, draft, delivery time and port restrictions; the current arithmetic does not validate those operations.
