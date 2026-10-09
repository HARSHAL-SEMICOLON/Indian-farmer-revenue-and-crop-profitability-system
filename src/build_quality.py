"""Data-quality, coverage, validation and source register tables."""
import numpy as np
import pandas as pd
from .config import PROC, CURATED

OFFICIAL_2019 = {  # PIB 3rd Advance Estimates 2019-20 (PRID=1624044); Mt, cotton million bales
    "Rice": 117.94, "Wheat": 107.18, "Maize": 28.98, "Gram": 10.90, "Soyabean": 12.24,
    "Rapeseed & Mustard": 8.70, "Sugarcane": 358.14, "Cotton": 36.05}
OFFICIAL_SRC = "PIB 3rd Advance Estimates 2019-20, https://www.pib.gov.in/PressReleasePage.aspx?PRID=1624044"

SOURCES = [
    ("APY", "District-wise, season-wise crop production statistics (Area, Production, Yield)",
     "DES, Ministry of Agriculture & FW (via data.gov.in / data.desagri.gov.in)", "1997-98 to 2019-20",
     "District x season x crop", "Production, area, yield",
     "Mirror github.com/Aditya12084/Crop-Statistics-India (1997-2019); a later DES vintage - ~17% of state-year-crop totals differ from the data.gov.in 1997-2015 release",
     "https://www.data.gov.in/catalog/district-wise-season-wise-crop-production-statistics-0",
     "District sums diverge from DES all-India estimates for some crops/years (see dq_validation); 2019 provisional"),
    ("MSP", "Minimum Support Prices / FRP", "CACP & DA&FW (PIB, DES, data.gov.in)", "2002-03 to 2024-25",
     "Crop x crop year", "Price benchmark, gross value estimate, MSP comparison",
     "Transcribed from official releases (see data/curated/msp_sources.csv)", "https://www.pib.gov.in/",
     "2003-04 not available; bonus treatment varies by source; 2 secondary values flagged"),
    ("COC", "Cost of cultivation / production - principal crops", "DES Cost of Cultivation Scheme (CACP)",
     "2008-09 to 2013-14", "State x crop", "A2+FL and C2 costs; profit estimates",
     "data.gov.in release mirrored at github.com/nitinvbharti/Agriculture_Analysis",
     "https://www.data.gov.in/", "Only 10 crops x 5 states each; no projection performed"),
    ("CMO", "Maharashtra APMC monthly arrivals & prices", "Govt. of Maharashtra APMC data (OGD hackathon release)",
     "Sep-2014 to Nov-2016", "APMC x commodity x month", "Price trends, volatility, MSP comparison, MH mandi valuation",
     "Mirror github.com/vibhor98/Analysis-of-agricultural-trends-in-time-series-dataset",
     "https://www.data.gov.in/", "Single state; original publisher page not re-verified"),
    ("AGM", "Current Daily Price of Various Commodities from Various Markets (Mandi)", "AGMARKNET / DMI via data.gov.in",
     "30-Sep-2024 (single day)", "Market x commodity x variety", "Cross-market dispersion, MSP comparison",
     "Mirror github.com/csePriyanshu/India-mandi-data-visualization",
     "https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi",
     "One-day cross-section; no arrivals quantity"),
    ("AGM26", "Current Daily Price of Various Commodities from Various Markets (daily accumulation)", "AGMARKNET / DMI via data.gov.in API",
     "21-Jul-2026 to 24-Sep-2026", "Market x commodity x variety x day", "Recent MSP gap, cross-market dispersion, daily volatility",
     "github.com/herrrickshaw/agri-commodity-tracker (commit 9b81fb7, data/mandi_prices_snapshot.csv)",
     "https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi",
     "No arrival quantities; exact duplicate rows dropped; first two days are partial pulls"),
    ("CPI", "Consumer price index, India (2010 = 100)", "World Bank WDI FP.CPI.TOTL (IMF IFS)", "2000-2025", "India x year",
     "Deflate gross value to constant 2018-19 rupees", "World Bank API", "https://api.worldbank.org/v2/country/IND/indicator/FP.CPI.TOTL",
     "Headline CPI, not a farm-specific deflator"),
    ("IMD", "Sub-divisional monthly rainfall 1901-2015", "India Meteorological Department (via data.gov.in)",
     "1901-2015", "Met subdivision x year x month", "Rainfall vs yield association",
     "Mirror github.com/MainakRepositor/Datasets", "https://www.data.gov.in/",
     "Subdivision != state; normal = 1951-2000 mean of this series (not IMD official LPA)"),
    ("PIB_AE", "Advance estimates of production 2019-20", "DA&FW via PIB", "2019-20", "All-India x crop",
     "Validation of district totals", "Direct", "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1624044", ""),
]


def main():
    prod = pd.read_csv(PROC / "fact_production.csv")
    crop = pd.read_csv(PROC / "dim_crop.csv")
    dq_p = pd.read_csv(PROC / "dq_production_issues.csv")
    dq_pr = pd.read_csv(PROC / "dq_price_issues.csv")
    dcy = pd.read_csv(PROC / "fact_district_crop_year.csv")
    scy = pd.read_csv(PROC / "fact_state_crop_year.csv")
    msp = pd.read_csv(CURATED / "msp_official_curated.csv")
    xchk = pd.read_csv(PROC / "dq_msp_crosscheck_2013.csv")

    issues = []
    for (iss, act), n in dq_p.groupby(["issue", "action"]).size().items():
        issues.append(("Production (APY)", iss, act, int(n), ""))
    for f, n in dq_pr.groupby("dq_flag").size().items():
        issues.append(("Mandi prices", f.split(":", 1)[1].strip(), f.split(":")[0], int(n), ""))
    for _, r in pd.read_csv(PROC / "dq_price_dedup.csv").iterrows():
        issues.append(("Mandi prices", "Repeated quote for the same market x commodity x variety x day (exact copies, or same price under two grades)",
                       "dropped before load (FAQ grade kept)", int(r.rows_dropped), r.source_dataset))
    for _, r in xchk[~xchk["match"]].iterrows():
        issues.append(("MSP", f"CMO vs PIB mismatch for {r['msp_key']} 2013-14 ({r['cmo_2013']} vs {r['pib_2013']})",
                       r["resolution"], 1, r["reason"]))
    issues.append(("MSP", "Crop year 2003-04 MSP not in available official files", "Year not MSP-valued", 1, ""))
    issues.append(("MSP", "Kharif 2015-16 pulse bonus (Rs 200) not verified", "bonus = NULL, base MSP used",
                   3, "Tur, Moong, Urad"))
    n_sec = int((msp.verification == "secondary").sum())
    issues.append(("MSP", "Values from secondary (news) sources", "kept, flagged verification='secondary'", n_sec,
                   "; ".join(msp.loc[msp.verification == 'secondary', 'msp_key'] + " " +
                             msp.loc[msp.verification == 'secondary', 'crop_year'].astype(str))))
    issues.append(("Production (APY)", "Production file is a later DES vintage than the data.gov.in 1997-2015 release; ~17% of overlapping state-year-crop totals differ",
                   "Later vintage used (older release has incomplete final years); comparison in notebook 01", 0, ""))
    issues.append(("Production (APY)", "Horticulture (onion, potato) largely absent from APY after ~2003",
                   "No gross value for non-MSP crops", 0, "Horticulture is reported via NHB, not APY"))
    issues.append(("Production (APY)", "State reorganisations: AP/Telangana (2014), MP/Chhattisgarh, Bihar/Jharkhand, UP/Uttarakhand (2000)",
                   "dim_state.state_group provided for consistent trends", 0, ""))
    issues.append(("Cost", "Cost data only 2008-09..2013-14 for 10 crops x 5 states", "Profit not estimated elsewhere", 0, ""))
    issues.append(("Weather", "Rainfall ends 2015; states mapped to IMD subdivisions (unweighted mean)",
                   "Rain-yield analysis limited to 1997-2015", 0, ""))
    dq = pd.DataFrame(issues, columns=["domain", "issue", "action", "n_rows", "detail"])
    dq.insert(0, "issue_id", range(1, len(dq) + 1))

    # coverage
    cov = []
    yr = prod.groupby("crop_year").agg(rows=("production_id", "size"), districts=("location_id", "nunique"))
    for y, r in yr.iterrows():
        cov += [("Production", "crop_year", str(y), "rows", r.rows), ("Production", "crop_year", str(y), "districts", r.districts)]
    vb = dcy.groupby("valuation_basis").size()
    for k, v in vb.items():
        cov.append(("Valuation", "valuation_basis", k, "district_crop_year_rows", v))
    w = dcy[dcy.crop_year.between(2004, 2019)]
    share = w.groupby("crop_year").apply(lambda x: x.gross_value_msp_inr.notna().mean())
    for y, v in share.items():
        cov.append(("Valuation", "crop_year", str(y), "share_rows_msp_valued", v))
    cov.append(("Cost", "all", "state_crop_years_with_profit", "rows", int(scy.est_profit_c2_per_ha.notna().sum())))
    cov.append(("Weather", "all", "state_crop_years_with_yield_anomaly_and_rain", "rows",
                int((scy.yield_anomaly_pct.notna() & scy.season_rain_dep_pct.notna()).sum())))
    coverage = pd.DataFrame(cov, columns=["domain", "dimension", "member", "metric", "value"])

    # validation vs official 2019-20 estimates
    nat = scy[scy.crop_year == 2019].groupby("crop_name").production_apy_unit.sum() / 1e6
    val = []
    for c, off in OFFICIAL_2019.items():
        ds = nat.get(c, np.nan)
        diff = (ds / off - 1) * 100
        val.append(("District sum vs DES all-India estimate", c, 2019, round(ds, 2), off,
                    "million bales (170 kg)" if c == "Cotton" else "million tonnes", round(diff, 1), OFFICIAL_SRC,
                    "consistent (within 10%)" if abs(diff) <= 10 else "divergent (>10%)"))
    validation = pd.DataFrame(val, columns=["check_name", "crop_name", "crop_year", "dataset_value", "official_value",
                                            "unit", "diff_pct", "official_source", "status"])
    src = pd.DataFrame(SOURCES, columns=["source_id", "dataset", "publisher", "coverage", "grain", "used_for",
                                         "access_route", "url", "reliability_note"])

    dq.to_csv(PROC / "dq_issues.csv", index=False)
    coverage.to_csv(PROC / "dq_coverage.csv", index=False)
    validation.to_csv(PROC / "dq_validation.csv", index=False)
    src.to_csv(PROC / "ref_sources.csv", index=False)
    print(validation[["crop_name", "dataset_value", "official_value", "diff_pct", "status"]].to_string())


if __name__ == "__main__":
    main()
