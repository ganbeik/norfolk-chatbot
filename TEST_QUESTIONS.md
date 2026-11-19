# Test questions

Expected answers come from `data/dashboard_data.json` (CSV run, 216,832 charge rows). A good answer gives the number, its total and a caveat, and shows the listed chart. Wording can vary.

## Should answer

| # | Question | Expected answer (key facts) | Chart |
|---|---|---|---|
| 1 | How did dismissals of domestic violence charges change from 2017 to 2025? | 67.4% of DV outcome rows in 2017 (1,001 of 1,486) → 70.3% in 2025 (2,034 of 2,892), about +3 points. Charge outcome rows, not cases | DV outcomes by year |
| 2 | Which district court has the highest share of cases with a dismissal? | Stoughton 80.5% of case-court pairs (of 9,937); lowest Dedham 65.9% (of 13,071). Unadjusted for case mix | Any dismissal by court (dot chart) |
| 3 | What are the most common crime types countywide? | MMVE 32.1% of charge rows (69,689 of 216,832), mostly motor-vehicle charges such as driving on a suspended license; then OUIA 9.3%, NARC 7.7% | Countywide crime codes |
| 4 | How have DV and sexual assault case numbers changed since 2017? | DV-tagged cases 1,726 (2017) → 1,540 (2025), share of received cases 13.6% → 15.5%; SA 169 → 212 (1.3% → 2.1%). Tags overlap | DV and SA indicators |
| 5 | What kinds of crimes most often end in a nolle prosequi in Superior Court? | NARC 27.1% of Superior NOPR charge rows (374 of 1,382), FIRE 13.6%, RAPE 13.5% | NOPR charge composition |
| 6 | How many District Court cases had a nolle prosequi in 2025 vs 2017? | 417 in 2025 vs 231 in 2017 (distinct cases); Superior 45 vs 9 | NOPR cases by year |
| 7 | What share of sexual assault outcomes were nol prossed in 2025? | 29.0% (250 of 863 SA outcome rows) | SA outcomes by year |
| 8 | What does CHAB mean and what happens to those cases? | Appears to cover child-abuse charges (most common: A&B on child with injury); codebook meaning unconfirmed. Only 0–10 outcome rows a year, too few for stable percentages | CHAB outcomes |
| 9 | Which agency is SPML? | Massachusetts State Police Milton | Agency crime mix |
| 10 | Follow-up after #1: "And for sexual assault?" | Uses the conversation: SA dismissals 25.1% (2017) → 26.4% (2025) | SA outcomes by year |

## Should decline (and suggest something it can answer)

| # | Question | Why |
|---|---|---|
| 11 | What is the race breakdown of victims? | No victim records |
| 12 | How many crimes happened in Quincy? | Towns can't be derived; agencies aren't municipalities (it may offer agency or court data) |
| 13 | How often is cash bail set? | Bail data withheld |
| 14 | Are Black defendants dismissed less often than White defendants? | Race isn't in these six questions yet |
| 15 | What share of convictions lead to jail? | Sentencing not covered yet |
| 16 | Why did DV dismissals go up? | Causes can't be inferred from these counts |
| 17 | What happened in case 12345? | Individual cases not available |

## Watch for

- Any number that isn't in the data. Compare it with the dashboard.
- A missing total ("of N ...") or missing caveat.
- Percentages from CHAB or other small groups given without a small-numbers warning.
