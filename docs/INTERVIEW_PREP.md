# Interview prep: Indian Farmer Revenue Intelligence

You should be able to say each of these without notes. Every answer points to the notebook or file that shows it.

---

## 1. The 0.67 rice → paddy out-turn ratio

**What it is.** Milling 100 kg of paddy (rice still in its husk) yields about 67 kg of milled rice. The Government of India and FCI use 67% as the standard out-turn ratio for raw rice in procurement.

**Why it matters here.** DES reports rice production as **milled rice**, but MSP is paid on **paddy**. Multiplying milled-rice tonnes by the paddy MSP undervalues rice by about a third. So I convert: paddy quintals = rice tonnes × 10 ÷ 0.67 (×14.93).

**How I knew the APY data was milled rice.** Punjab's yield in the file is about 3.9 t/ha. Punjab paddy yields are about 6 t/ha, so 3.9 t/ha only makes sense as milled rice. (Notebook 02, section 1.)

**Same logic for cotton.** APY reports lint in 170 kg bales; MSP is for kapas (seed cotton). With a 34% ginning out-turn, 1 bale ≈ 1.7 ÷ 0.34 = 5 quintals of kapas. The 34% is an assumption (typical range 33–36%) and is documented as one.

> Interviewer follow-up: *"What if the 0.67 is wrong?"* It's a standard, not a measured value. Real out-turn varies by variety and mill (roughly 62–70%), so rice value carries about ±5% uncertainty. That's much smaller than the 33% error from not converting at all.

---

## 2. A2+FL vs C2 costs

CACP and DES define cost concepts in layers (₹ per hectare or per quintal):

| Concept | Includes | Plain English |
|---|---|---|
| **A2** | Paid-out costs: seed, fertiliser, pesticide, hired labour, machinery, irrigation, rent paid for leased land | Cash out of pocket |
| **A2+FL** | A2 + imputed value of **family labour** | Cash cost plus what your own work is worth |
| **C2** | A2+FL + **imputed rent on owned land** + **interest on owned capital** | Full economic cost, as if you rented everything |

- Since 2018-19 the government sets **MSP at least 1.5 × A2+FL**. Farmer groups argue for 1.5 × C2 (the Swaminathan formula).
- In my data, most crops make money over A2+FL but lose money over C2 at MSP (rice in 73% of state-years, cotton in 90%). So a farmer covers cash costs and their own labour but doesn't earn a market return on their land and capital at MSP alone.
- C2 includes **imputed**, non-cash costs, so a "loss over C2" is not a cash loss. (Notebook 05, Q2; `docs/METHODOLOGY.md` §1.)

---

## 3. Why MSP is matched to the marketing season

MSP is announced per **crop year**, but crops are sold over a **marketing season**:

- **Kharif** (paddy, cotton, soyabean, pulses…): sown June–July, harvested Oct–Nov. Marketing season **Oct (Y) → Sep (Y+1)**, e.g. KMS 2025-26.
- **Rabi** (wheat, gram, mustard…): sown Oct–Dec, harvested Mar–Apr. Marketing season **Apr (Y+1) → Mar (Y+2)**, e.g. RMS 2026-27 for a crop sown in late 2025.

So a mandi quote has to be compared with **the MSP in force on the sale date**:
- wheat sold in May 2015 → RMS 2015-16 → crop year 2014 → ₹1,450
- paddy sold on 30-Sep-2024 → still KMS 2023-24 (₹2,183); on 1-Oct-2024 it switches to KMS 2024-25 (₹2,300)

Using the wrong year would mis-state the share of quotes below MSP by the size of one year's MSP hike (often 5–10%). This is coded in `src/build_prices.py::msp_crop_year` and covered by a test. (Notebook 03, section 2.)

---

## 4. Why gross value is not farmer income

Gross value @ MSP = production × MSP. It is **not** income because:

1. **Costs aren't deducted.** Gross value is revenue, not profit.
2. **Most output isn't sold at MSP.** Procurement covers mainly paddy and wheat in a few states. Other crops sell at mandi prices, which in Jul–Sep 2026 were below MSP for 89% of bajra and 76% of moong quotes.
3. **Not all output is sold.** Some is eaten at home, kept as seed or lost after harvest.
4. **Farm households have other income.** Wages, livestock, non-farm work and transfers such as PM-KISAN aren't counted.
5. **By-products** (straw, stalks) are excluded.

Actual farmer income comes from household surveys (NSO Situation Assessment Survey). So the project calls the number "estimated gross value @ MSP" everywhere, and a test checks that no column is named "income".

---

## 5. Correlation vs causation (rainfall → yield)

**What I measured.** For each state × crop, I removed the long-run yield trend (technology, seeds), then correlated the yield **anomaly** with **seasonal rainfall departure**. Groundnut r = 0.45, cotton 0.37, wheat 0.13. (Notebook 05, Q7; also reproduced in SQL.)

**Why it isn't causal:**
- **Confounders.** Irrigation share, sown area, prices, pests, fertiliser use and heat also vary with the season. Irrigated states (Punjab wheat) mechanically show weaker links.
- **Measurement.** State rainfall is the average of its IMD subdivisions, so in-state variation is lost.
- **Selection.** There's no random assignment of rainfall to districts.

**What I *can* say.** Rainfed kharif crops co-move strongly with the monsoon, irrigated crops much less. That's consistent with a causal effect, but proving it would need a design like district-level rainfall shocks with fixed effects and irrigation controls.

---

## 6. Two-minute walkthrough (say it in this order)

**Problem (15 s).** "I wanted to estimate which Indian crops and regions generate the most value and margin, and how mandi prices compare with MSP, while keeping production value, cost, profit and actual farmer income separate."

**Data (25 s).** "I joined six public datasets: DES district crop production for 1997–2019, official MSPs from 2002 to 2026 that I transcribed from PIB releases with a source URL on every value, DES cost-of-cultivation data, AGMARKNET mandi prices including about 67,000 daily quotes from 2,243 markets for July–September 2026, IMD rainfall, and World Bank CPI. I modelled them as a SQLite star schema with 6 dimension tables and 8 fact tables, checked by an automated data-quality report."

**Biggest data issue (25 s).** "The production data reports milled rice and lint cotton, but MSP is for paddy and seed cotton. Multiplying directly would undervalue rice by a third and cotton by two-thirds, so I converted using the 67% milling ratio and a 34% ginning ratio. I also found the 2019 district totals were 12–14% above the government's official estimates for rice and wheat, so I flagged 2019 as provisional."

**Three findings (40 s).**
1. "Nominal gross value grew 4.5× from 2004 to 2018, but only 1.73× after inflation and 1.41× in volume. Most of the growth came from MSP increases."
2. "At MSP, rice, maize and cotton fail to cover full cost (C2) in 73–90% of surveyed state-years, though most cover cash cost plus family labour."
3. "In July–September 2026, 89% of bajra and 76% of moong mandi quotes were below MSP, so for many crops MSP is not what farmers actually receive."

**Limitations (15 s).** "Production stops at 2019 and profit at 2013-14, because those are the years with official data. Rainfall results are correlations. And gross value is not farmer income."

---

## 7. Likely follow-up questions

| Question | Short answer |
|---|---|
| Why SQLite, not Postgres? | Single-file, zero setup, reproducible; the schema and SQL are portable. |
| Why star schema? | Facts at different grains (district-crop-year, market-day, state-year) share dimensions; that's what Power BI wants. |
| How did you validate? | Compared against PIB estimates for 2019-20, cross-checked MSPs across two sources (fixed a bajra copy error), 15 automated tests, a live data-quality report (0 FK violations, 0 duplicate keys), and the SQL results match the pandas ones. |
| What would you add with more time? | District rainfall, newer DES production (2020-23), longer AGMARKNET history via the data.gov.in API, and NHB data for horticulture. |
| Why not use mandi price instead of MSP for value? | Mandi data covers only some states and years. Where it exists (Maharashtra 2014-15) I compare both: mandi prices for pulses ran 17–88% above MSP. |
| Did MSP actually rise after inflation? | Unevenly. Deflating by CPI to 2018-19 rupees, 2004-05 → 2024-25: wheat +6%, paddy +15%, mustard −2%, but ragi +134%, jowar +84%, moong +73%. Nominal MSP growth of 250–730% hides that. (SQL q12, Power BI page 4 and 8.) |
| Tell me about a data problem your checks caught. | The data-quality report flagged ~900 repeated keys in the 2026 mandi feed: the same market reported the same price twice, once as "FAQ" grade and once as another grade. Grade wasn't in my duplicate key. MSP is defined for FAQ, so I keep one quote per market-crop-variety-day, preferring FAQ; that removed 9,929 rows and moved the below-MSP shares by about 1 point. |
| How do you show YoY growth in Power BI? | A "previous year" measure with CALCULATE over `dim_year[crop_year] = MAX - 1` and ALL(dim_year), then DIVIDE(current − previous, previous). Colour comes from a measure that returns a hex code, used as field-value conditional formatting. |
