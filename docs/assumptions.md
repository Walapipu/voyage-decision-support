# Modelling assumptions

Updated 28 October 2026 from the clarification supplied by Yi Heng. Results are feasible **under these working assumptions**, not operational approvals.

## Assumption log

| ID | Working assumption pending Cargill | Effect | Configuration |
|---|---|---|---|
| A-01 | Shortfalls are covered by the voyage-level planning purchase, with no extra bunkering days, charges or diversion. | Opening-ROB shortages remain visible but do not exclude combinations. No delivery location or schedule is invented. | `fuel_policy = "planning_purchase"`; `"opening_rob_only"` restores strict diagnostic exclusion. |
| A-02 | Exclude arrival after laycan closing outright. | Excluded combinations and reasons remain visible/exportable. No extensions or penalties. | `laycan_policy = "exclude_late"`; unsupported alternatives fail validation until implemented. |
| A-03 | Apply 0.30 m to summer draft; report port comparisons separately. | Summer-draft failure excludes. Port warnings are report-only, with no added port margin by default. | `port_draft_policy = "report_only"`; `"exclude"` enables a hard check if later authorised. `port_draft_margin_m = "0.00"` is separate from the CSV summer margin. |

Edit **config/modelling.toml** to change working policy, then restart the app. Active policy is displayed below and included in calculation outputs and methodology exports. The required summer margin remains sourced from commercial_assumptions.csv. Do not change source inputs unless the supplied assumptions change.

## Confirmed arithmetic

**Purchases:** max(0, consumption + reserve − opening remaining-on-board fuel), separately for VLSFO and MGO. This is a voyage-level balance, not a delivery schedule.

**Bunker expense:** consumption × monthly reference price, not purchase × price. CHECK-01 consumes approximately 987.251 t VLSFO and 46.817 t MGO at USD 499/t and USD 664/t. Full-precision consumption reproduces USD 523,724.60; rounded displayed tonnes can give a slightly different result. Purchases are not charged a second time.

The loading port's assigned regional price proxy and explicitly selected month (default March 2026) price the consumption. The proxies are not bunkering-stop recommendations.

**Timing:** load-port arrival = availability + ballast days. Early arrival waits until laycan start. Loading then takes lift ÷ loading rate + turn time. Total voyage days = ballast + waiting + loading + laden + discharge. NOR and readiness/start-loading milestones are not modelled separately. Arrival exactly at closing passes; loading need not finish by closing. No extra bunkering time, charges or diversion are included.

**Departure deadweight:** lift + laden-leg VLSFO and MGO at sea + 300 t VLSFO reserve + 25 t MGO reserve + 3,000 t other deadweight.

**Sailing draft:** ballast draft + (summer draft − ballast draft) × departure deadweight ÷ DWT.

CHECK-01 gives departure deadweight 167,850.078 t, estimated draft 17.383 m, and summer-draft margin approximately 0.717 m. Full precision is retained. Port consumption is included in consumption/purchases but excluded from this confirmed departure-deadweight formula. Discharge uses about 18.9 t VLSFO; do not silently add it to the validated draft formula.

## Fuel diagnostic

The engine still projects opening ROB **without replenishment** through ballast, waiting, loading, laden and discharge, separately by grade. Negative balances show unmet demand in this diagnostic, not assumed actual inventory after purchasing. It reports the first shortage and estimated exhaustion time. Port MGO use is zero under the supplied formulas.

For CHECK-01, 438 t opening VLSFO versus 458.829 t ballast consumption leaves a **20.829 t shortfall before the loading port**. Keeping 300 t on arrival would require 320.829 t before ballast. The total planned VLSFO purchase is 849.251 t under either interpretation. A-01 assumes replenishment covers the shortage with no added days/cost, without inventing its timing/location.

The purchase formula preserves the final balance including reserves. It does not prove continuous reserve maintenance. No artificial delivery schedule is added to make diagnostic balances positive.

## Port draft reporting

For loading and discharge ports, report the limit, the single laden-departure draft, and headroom (limit minus that draft). This is separate from the summer-draft check. Default A-03 reports a warning without excluding the combination or applying 0.30 m to port limits.

The discharge comparison uses a departure-draft proxy, not a calculated discharge-arrival draft. Current-port draft is not evaluated: applying a future loaded draft at the ballast starting port would misrepresent the stage. Port warnings remain visible when core checks pass.

## Awaiting Cargill

- How to cover the pre-loading shortfall and which bunkering locations are allowed.
- Whether reserves must be maintained throughout or at specified milestones.
- Whether 0.30 m applies to port limits, and at which stages.
- Whether late arrival excludes combinations or permits extensions/penalties.
- Whether bunkering adds time/cost, and which location/month prices purchases at different stages.

Until those answers arrive, A-01 to A-03 govern. The previous strict opening-ROB exclusion and minimum-of-summer/port draft rule are superseded as defaults. CHECK-01 remains an arithmetic reference, not an allocation recommendation.
