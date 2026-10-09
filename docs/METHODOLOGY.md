# Methodology, assumptions & limitations

## 0. Pipeline

```text
Data collection      data/raw/ (official releases and mirrors, provenance in data/raw/SOURCES.md)
      ↓
Cleaning             duplicates, impossible values, state/district names, incomplete years    src/build_production.py, build_prices.py
      ↓
Unit standardisation milled rice → paddy, lint bales → kapas, tonnes → quintals              src/config.py (CROPS registry)
      ↓
Validation           marketing-season MSP rule, outliers, totals vs official estimates       src/build_quality.py
      ↓
SQLite database      star schema: 6 dimensions, 8 facts, quality tables                     sql/schema.sql, src/load_db.py
      ↓
Python + SQL analysis  business questions in pandas and in SQL, cross-checked by tests      src/analytics.py, sql/analysis_queries.sql
      ↓
Quality report       live checks → docs/DATA_QUALITY.md                                     src/dq_report.py
      ↓
Power BI             8-page PBIP report, 81 DAX measures                                     power_bi/build_pbip.py
      ↓
Business insights    README, outputs/results/findings.md
```

`python run_pipeline.py` runs every step in this order.

## 1. Concepts, kept deliberately separate

| Concept | What it means here | Where |
|---|---|---|
| **Production** | Physical output reported by DES APY (tonnes; cotton in 170-kg *lint* bales; jute in 180-kg bales; rice as *milled* rice) | `fact_production`, `fact_district_crop_year` |
| **Market price** | Modal mandi price (Rs/qtl) reported by APMC/AGMARKNET for a market-day or market-month | `fact_market_price` |
| **MSP** | Government Minimum Support Price (FRP for sugarcane), Rs/qtl, by crop year | `fact_msp` |
| **Estimated gross value @ MSP** | Production (converted to the MSP commodity form) × MSP of that crop year. A *benchmark valuation*: it assumes every quintal earns exactly MSP | `gross_value_msp_inr` |
| **Estimated gross value @ mandi** | Production × arrival-weighted modal mandi price (Maharashtra, crop years 2014–15 only) | `gross_value_mandi_inr` |
| **Production cost** | DES Cost of Cultivation Scheme: A2+FL (paid-out + imputed family labour) and C2 (comprehensive, incl. imputed rent and interest on owned land/capital), Rs/ha and Rs/qtl | `fact_cost_of_cultivation` |
| **Estimated profit** | Gross value @ MSP per ha − cost per ha, **only** where a DES state × crop × year cost exists (2008-09 to 2013-14) | `est_profit_*` |
| **Actual farmer income** | **Not estimated.** It would need realised sale prices and quantities sold, procurement coverage, by-product value, livestock, wages, non-farm income and transfers (NSO Situation Assessment Survey territory). Nothing in this project should be read as farmer income. | — |

## 2. Sources

| Dataset | Publisher | Coverage | How obtained | Reliability notes |
|---|---|---|---|---|
| District-wise season-wise crop production (APY) | DES, MoA&FW (data.gov.in / data.desagri.gov.in) | 1997-98 to 2019-20, 760 district names, 36 states/UTs | GitHub mirror of a later DES APY export (1997-2019). It is **not** identical to the older data.gov.in 1997-2015 release: about 17% of state-year-crop totals differ (revisions, district re-mapping). The older release has clear gaps in its last years (e.g. wheat 2014-15 = 42 Mt vs 85 Mt; gram 2.8 vs 6.5 Mt), so the later vintage is used. See notebook 01 | District sums ≠ DES all-India estimates for some crop-years (see §6) |
| MSP / FRP | CACP, DA&FW (PIB releases, DES, data.gov.in) | crop years 2002-03, 2004-05 to **2026-27** (KMS 2026-27, RMS 2027-28) | Parsed from data.gov.in/CMO files (2002-2015) and transcribed from official PIB/DES releases (2016-2026). Every row stores its source URL | 2003-04 missing; secondary values: FRP 2019-20, jute 2017-18, and RMS 2027-28 (announced 30-Sep-2026; two news reports agree, PIB page to be linked). RMS 2027-28 costs not stored (only margins were reported) |
| Cost of cultivation | DES (CACP scheme) | 2008-09 to 2013-14; 10 crops × 5 major states each | data.gov.in release (mirror) | Survey yields differ from APY yields (ratio 0.7–1.05) |
| Maharashtra APMC monthly prices | Govt. of Maharashtra APMC data (OGD hackathon release) | Sep-2014 to Nov-2016, 349 APMCs | Mirror | Single state |
| AGMARKNET daily prices | DMI / AGMARKNET via data.gov.in | 30-Sep-2024 (one day) and **21-Jul to 24-Sep-2026** (daily, 2,243 markets, ~35,500 MSP-comparable quotes) | Mirrors of the OGD "current daily price" resource (2026: github.com/herrrickshaw/agri-commodity-tracker, commit 9b81fb7) | No arrival quantities; repeated quotes for the same market x commodity x variety x day dropped (same price under two grades: FAQ kept) |
| Consumer price index | World Bank WDI `FP.CPI.TOTL` (India CPI via IMF IFS) | 2000-2025, 2010 = 100 | World Bank API | Used only to deflate to constant 2018-19 rupees |
| Sub-divisional monthly rainfall | IMD via data.gov.in | 1901-2015, 36 subdivisions | Mirror | Ends 2015 |
| Production estimates 2019-20 (validation) | DA&FW via PIB | 2019-20 | PIB release | Used only to validate |

*Why mirrors:* the government portals (data.gov.in, agmarknet.gov.in, desagri.gov.in, cacp.da.gov.in) were not reachable from the build environment, and data.gov.in downloads require a sign-in. The mirrors are copies of those government releases and were cross-checked where possible. Re-downloading the same resources directly from data.gov.in will reproduce the inputs.

## 3. Unit compatibility (checked before any multiplication)

Why it matters: MSP is announced per quintal of a specific commodity form, but APY reports production in a different form for some crops. Multiplying APY rice (milled) by the paddy MSP undervalues rice by a third, because one tonne of milled rice comes from about 1.49 tonnes of paddy. Multiplying cotton lint bales by the kapas MSP per quintal undervalues cotton almost threefold, because a 170-kg lint bale comes from about 5 quintals of seed cotton. Every conversion below is applied before any production × price multiplication, and `src/dq_report.py` checks the factors on every run.

| Crop | APY unit | MSP / mandi unit | Conversion used | Note |
|---|---|---|---|---|
| Rice | tonnes of **milled rice** (Punjab ≈ 3.9 t/ha confirms milled basis) | Rs/qtl of **paddy** | paddy qtl = rice t × 10 ÷ 0.67 | 67% = FCI/GoI out-turn ratio for raw rice |
| Cotton | bales of 170 kg **lint** | Rs/qtl of **kapas** (seed cotton) | kapas qtl = bales × 1.70 ÷ 0.34 (= 5.0 qtl/bale) | 34% ginning out-turn assumed (typical 33–36%; ±1 pt ≈ ∓3% value) |
| Jute | bales of 180 kg | Rs/qtl raw jute | × 1.8 | Mesta not valued |
| Sugarcane | tonnes of cane | FRP Rs/qtl of cane | × 10 | FRP is a floor; many states pay a higher SAP, and FRP is linked to recovery (9.5% → 10%) |
| Groundnut | tonnes in pods | MSP for groundnut-in-shell | × 10 | |
| All others | tonnes | Rs/qtl of whole grain/seed | × 10 | |

Mandi rows are tagged with `price_form`; only forms matching the MSP form are compared with MSP. Milled rice, basmati paddy, dal, ginned cotton, kernels and organic lots are excluded.

## 4. Time alignment

* `crop_year` = first year of the agricultural year (2016 = 2016-17), the same as APY's `year`.
* MSP joins on crop year. Kharif crop of 2016-17 → KMS 2016-17. Rabi crop sown in 2016-17 → RMS 2017-18.
* **MSP applicable to a mandi quote** follows the marketing season of the sale date. Kharif: Oct(Y)–Sep(Y+1) → crop year Y. Rabi: Apr(Y+1)–Mar(Y+2) → crop year Y. So on 30-Sep-2024, paddy is compared with KMS 2023-24 (₹2,183) and wheat with RMS 2024-25 (₹2,275).
* Bonuses are stored separately (`bonus`). `msp_effective = msp_base + bonus`. The kharif 2015-16 pulse bonus could not be verified, so it is left NULL and base MSP is used.

## 5. Analytical choices

* **Valuation window 2004-05 to 2019-20.** That is the contiguous official MSP series. 2019-20 is flagged *provisional*, and the default report window is 2004–2018.
* **Profit** uses APY state yield × MSP − DES cost/ha. Two known biases:
  1. **MSP valuation understates crops whose market price exceeded MSP.** For example, Maharashtra tur sold at +32% (2014-15) and +88% (2015-16) above MSP. A "loss over C2" at MSP is not a loss at market prices.
  2. CoC survey yields are usually higher than APY yields (median ratio APY/CoC 0.72–1.05), while cost/ha is the survey's. This pushes profit down.
  
  By-product value (straw, stalks) is excluded from revenue but included in CoC cost/ha. C2 includes imputed rent and interest on owned assets, so it is not a cash cost.
* **Growth decomposition**: ln(value) = ln(area) + ln(yield) + ln(price). Comparing 3-year means (2004-06 vs 2016-18) gives the share of value growth from each.
* **Rainfall–yield**: state rainfall = unweighted mean of the state's IMD subdivisions. Departure is relative to the 1951-2000 mean *of this series* (not IMD's official LPA). The rain metric is matched to season: kharif crops → Jun–Sep; rabi crops → Oct–Dec of the sowing year + Jan–Feb of the next year. Yield is detrended per state × crop with a linear trend (≥10 years, ≥10,000 ha avg). Results are Pearson/Spearman correlations and OLS slopes. **These are associations, not causal effects.** Irrigation share, sowing shifts, prices, pests and technology are not controlled for, and irrigated states will mechanically show weaker links.
* **Inflation**: real values = nominal ÷ CPI deflator. Crop year Y uses the mean of calendar-year CPI for Y and Y+1, rebased so 2018-19 = 100 (`gross_value_real_2018_inr`). Three views are reported side by side: nominal, real (CPI) and volume (constant 2018-19 MSP). real ÷ volume = how much MSP outpaced consumer prices.
* **Volatility**: coefficient of variation of monthly modal price per APMC × commodity (≥18 months), intra-month (max−min)/modal spread, mean absolute month-on-month change. Cross-market dispersion uses the 30-Sep-2024 snapshot (CV, p90/p10).

## 6. Data quality & validation (also on report page 6)

* The production file is a later DES vintage than the data.gov.in 1997-2015 release; ~17% of overlapping state-year-crop totals differ (notebook 01, section 3).
* 342 APY rows excluded: 219 from the incomplete 2020 year, 114 conflicting duplicate keys (both rows dropped; mostly Telangana 2015, North 24 Parganas), and 9 with implausible yields.
* Price rows: modal ≤ 0 and extreme outliers (>5× or <⅕ of the commodity median within the same dataset) are excluded, and min/modal/max inconsistencies are flagged (kept for modal, no spread computed). Current counts are in [`DATA_QUALITY.md`](DATA_QUALITY.md).
* MSP cross-check (CMO vs PIB, 2013-14): 18/20 match. Bajra corrected (CMO repeated the maize value). Sesamum kept at CMO 4,500 (PIB 2,500 breaks the series).
* **District totals vs DES 3rd advance estimates 2019-20:** rice +12%, wheat +14%, maize −29%, soyabean −17%; gram, mustard, sugarcane and cotton are within ±8%. Maize is under-captured in most years, and 2019 is provisional.
* State reorganisations (AP/Telangana 2014; MP/CG, Bihar/JH, UP/UK 2000) break state series. `dim_state.state_group` provides merged groups.
* Horticulture (onion, potato) is largely absent from APY after ~2003 (it is reported via NHB), so it is not valued. It still appears in price analysis.

## 7. Limitations (read before quoting a number)

1. Gross value @ MSP ≠ market value ≠ farmer income. Most output is not procured at MSP. Procurement is concentrated in paddy/wheat in a few states.
2. Profit exists only for 10 crops × ~5 states × 6 years (298 state-crop-years). It is not projected beyond that.
3. Market prices cover Maharashtra (Sep-2014 to Nov-2016), one national day (30-Sep-2024) and ten national weeks (21-Jul to 24-Sep-2026). There is no continuous national series for 2017-2025.
4. Rainfall ends in 2015, at subdivision resolution. There is no district rainfall and no irrigation data.
5. Real values use all-India headline CPI, not a farm-specific deflator (CPI-AL or the agricultural GDP deflator would be alternatives).
6. Production ends in 2019-20 because no complete district-level file for later years was publicly reachable when this was built (a 2009-2022 mirror was checked and rejected: it keeps only district-years with rainfall readings, so coverage swings from 116 to 550 districts a year). Newer DES/UPAg files can be dropped into `data/raw/apy_district_extra_*.csv` (see README).
7. District names are as reported. New districts carved out over time appear as separate districts from their first reporting year.
