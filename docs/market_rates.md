# Market rate assumptions

The brief asks us to state and justify the hire offers for the 11 market vessels and the freight quotations for the 8 market cargoes, because the data pack does not supply them. This page sets out what we assume, why, and where the numbers come from. The values in the tables below are calculated from the data pack each time the app starts, so they always match the engine.

## Anchor: the data pack's FFA references

Every market rate is derived from the FFA values in `ffa_reference.csv` (5TC in USD/day, and the C3, C5 and C7 voyage routes in USD/t). We use the pack's figures rather than live market data so that freight, hire and bunker prices all come from the same coursework market.

- **Assumption M1.** The FFA reference for a month (February and March 2026) or quarter (Q2 onwards) is the market level for any fixture in that period.
- **Limitation.** The pack's levels sit below the reported 2026 market. In mid-February 2026, the Baltic C5TC was reported near USD 28,800/day, C3 near USD 23.9/t and C5 near USD 9.3/t ([DCN, 13 Feb 2026](https://www.thedcn.com.au/news/baltic-exchange-weekly-report-13-february-2026)); C3 was near USD 30/t by 20 March ([DCN, 20 Mar 2026](https://www.thedcn.com.au/news/baltic-exchange-weekly-report-20-march-2026)). The pack has 15,250, 18.3 and 6.9 for February. Our quotes and offers therefore represent the pack's market, not a live one.

## Market vessel hire offers

- **Assumption M2.** A market vessel is offered at the 5TC index for its delivery month (all 11 vessels open in March 2026, so 5TC = USD 18,900/day).
- **Assumption M3.** The offer is adjusted for fuel efficiency against the pack-average Capesize, the mean economical-speed consumption of all 15 vessels. A vessel that burns less earns its daily fuel saving as a premium; one that burns more gives it up as a discount. VLSFO and MGO are valued at the Singapore price for the delivery month. The adjustment uses the average of laden and ballast consumption.
- **Assumption M4.** Offers are rounded to the nearest USD 50/day. They are gross; Capesize fixtures carry 5% total commission, 3.75% address plus 1.25% brokerage ([Baltic Circular 48/17](https://www.balticexchange.com/en/data-services/Circulars/market-announcements-/category-a/2017/circular-48-17--capesize-commission-change.html)). The engine's cost side does not charge brokerage on hire, matching how managed-vessel hire is treated.

**Why.** Spot and index-linked Capesize charters are priced off the 5TC index, with premiums or discounts for specification ([Dry Bulk, index-linked charter example](https://www.drybulkmagazine.com/shipping/11102022/himalaya-shipping-announces-time-charter-agreements-for-two-vessels)). Published analysis of Clarksons data (2019–2022) found eco Capesizes earned about 9% more time-charter hire than conventional ships ([Moutzouris et al., 2024](https://openaccess.city.ac.uk/id/eprint/33165/1/CID-Summer-2024-Moutzouris-etal-050924.pdf)). All 15 pack vessels have similar economical-speed specifications, so a fuel-value adjustment is a more measured way to tell them apart than a flat eco premium. The pack's vessels burn about 37–43 t/day at 12–12.9 knots. That is close to the Baltic's old 180k standard at 12 knots on 43 t ([route and vessel summary](https://bmti-report.com/?p=290)) and its 182k standard at 13 knots on 44 t ([Baltic Circular 21/24](https://www.balticexchange.com/en/data-services/Circulars/market-announcements-/category-a/2024/circular--21-24-consultation--summary-bci-vessel-and-c5tc-weight.html)), which supports 5TC as the base.

## Market cargo freight quotations

- **Assumption M5.** A freight quote is the rate that gives a pack-average Capesize a target daily earning (TCE) on that voyage. The benchmark voyage has the following parts:
  - a ballast leg back to the loading area, equal to the laden distance
  - the nominal cargo quantity
  - the cargo's own load and discharge rates, turn times, port costs and commission
  - economical speed
  - bunkers at the loading port's regional price proxy in the laycan month
- **Assumption M6.** A cargo on an FFA index route targets the TCE that route pays, implied by the route's FFA rate on an anchor cargo:
  - **C5** (West Australia–Qingdao) anchors on MC-01 Dampier–Qingdao, which is the C5 voyage. MC-07 Port Hedland–Gwangyang is the same trade and uses the same TCE.
  - **C3** (Tubarão–Qingdao) anchors on MC-02 Ponta da Madeira–Caofeidian, a Brazil–North China voyage of nearly the same distance.
- **Assumption M7.** Every other cargo targets 5TC for its laycan month, the market-average Capesize earning. No index route covers them: no Baltic route was found for Kamsar–India, Vancouver–China, Tubarão–Malaysia or Indonesia–India ([Baltic route descriptions, Circular 44/24](https://www.balticexchange.com/en/data-services/Circulars/market-announcements-/category-a/2024/circular--44-24-consultation--bci-route-descriptions.html)). Saldanha–Qingdao (C17) exists ([route summary](https://bmti-report.com/?p=290)), but the pack has no FFA value for it.
- **Assumption M8.** Quotes are rounded to the nearest USD 0.05/t. The cargo's own commission rate in the pack applies. The quote is a single rate with no half-freight rule or other special terms.

**Why.** Building each quote from a target TCE keeps every quote consistent with the pack's distances, bunker curve and port costs, so the quote moves when they do. Anchoring to the pack's C3 and C5 values reproduces those indices exactly on the cargoes that run on them. The C3 and C5 rates imply a higher TCE than 5TC because those are front-haul routes. That matches the market, where Brazil and Australia to China cargoes pay more per day than the 5TC average.

**Cross-check against published route relationships.** All cases are inside or near the observed range:

| Cargo | Our quote vs index | Market evidence |
|---|---|---|
| MC-03 Saldanha–Tianjin | 0.84 × C3 | Saldanha–Qingdao fixed at 0.77 × C3 ([Banchero Costa, 24 Oct 2025](https://www.steelorbis.com/steel-prices/steel-matters/october-20-27-2025-weekly-market-report-banchero-costa-1417070.htm)) |
| MC-06 Kamsar–Mangalore | 0.75 × C3 | Kamsar–North China fixed near 1.04 × C3 ([Banchero Costa, Jan 2025](https://www.steelorbis.com/steel-prices/steel-matters/january-6-13-2025-weekly-market-report-banchero-costa-1374513.htm)); India is a shorter haul |
| MC-08 Tubarão–Teluk Rubiah | 0.79 × C3 | About 9,950 nm against about 11,000 nm for C3 |
| MC-05 Vancouver–Fangcheng | 1.58 × C5 | No published index; built bottom-up only |
| MC-04 Taboneo–Krishnapatnam | 0.92 × C5 | Short haul with slow coal handling; [Platts assesses this trade separately](https://www.spglobal.com/energy/en/pricing-benchmarks/our-methodology/subscriber-notes/120122-platts-launches-capesize-thermal-coal-panamax-limestone-voyage-tce-assessments) |

## What these assumptions do not cover

- **Not live offers.** Every quote and offer is our assumption, not a counterparty offer. The real market spread for any one fixture can be several dollars per tonne.
- **Rerouting.** A market vessel's ballast to the loading port uses the pack's ballast distances, the same as for managed vessels.
- **Period cover.** Hire is for one voyage and is paid only for voyage days. We do not model idle time after the voyage, redelivery or a period charter.
- **C7 (Bolivar–Rotterdam).** No pack cargo runs on it, so it is not used.
- **Sensitivity.** A planned step series of hire and freight changes will show how far each assumption can move before a recommendation changes.

## Sources

- [Baltic Exchange, Circular 48/17](https://www.balticexchange.com/en/data-services/Circulars/market-announcements-/category-a/2017/circular-48-17--capesize-commission-change.html): Capesize routes move to 5% total commission (3.75% address plus 1.25% brokerage).
- [Baltic Exchange, Circular 21/24](https://www.balticexchange.com/en/data-services/Circulars/market-announcements-/category-a/2024/circular--21-24-consultation--summary-bci-vessel-and-c5tc-weight.html) and [Circular 19/25](https://www.balticexchange.com/en/data-services/Circulars/market-announcements-/category-a/2025/circular-19-25--market-announcement---c5tc-timeline.html): BCI 182k vessel specification and 5TC weightings from 2 January 2026.
- [Baltic Exchange, Circular 44/24](https://www.balticexchange.com/en/data-services/Circulars/market-announcements-/category-a/2024/circular--44-24-consultation--bci-route-descriptions.html): BCI route descriptions; [route summary](https://bmti-report.com/?p=290) including C17 Saldanha Bay–Qingdao.
- Banchero Costa weekly reports via SteelOrbis: [6–13 January 2025](https://www.steelorbis.com/steel-prices/steel-matters/january-6-13-2025-weekly-market-report-banchero-costa-1374513.htm) and [20–27 October 2025](https://www.steelorbis.com/steel-prices/steel-matters/october-20-27-2025-weekly-market-report-banchero-costa-1417070.htm).
- [Dry Bulk Magazine (2022)](https://www.drybulkmagazine.com/shipping/11102022/himalaya-shipping-announces-time-charter-agreements-for-two-vessels): index-linked Capesize time charters priced as index plus a premium.
- [Moutzouris et al. (2024)](https://openaccess.city.ac.uk/id/eprint/33165/1/CID-Summer-2024-Moutzouris-etal-050924.pdf): eco-ship time-charter premium in the Capesize market.
- DCN, Baltic Exchange weekly reports for [13 February 2026](https://www.thedcn.com.au/news/baltic-exchange-weekly-report-13-february-2026) and [20 March 2026](https://www.thedcn.com.au/news/baltic-exchange-weekly-report-20-march-2026): market levels quoted under Limitation.
- [S&P Global Platts (2022)](https://www.spglobal.com/energy/en/pricing-benchmarks/our-methodology/subscriber-notes/120122-platts-launches-capesize-thermal-coal-panamax-limestone-voyage-tce-assessments): Capesize Indonesia–West Coast India thermal coal assessment.

The Baltic Exchange site blocks automated reading, so its circulars were checked through search excerpts and secondary copies; confirm exact wording on the Baltic pages before quoting them.
