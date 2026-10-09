"""
Build fact_msp from official sources only.

Year convention: crop_year = first year of the agricultural year (July-June).
  Kharif crop of crop_year 2016 -> KMS 2016-17.   Rabi crop sown in crop_year 2016 -> RMS 2017-18.
This matches DES APY 'year' (2016 = 2016-17) so MSP and production join on the same key.

msp_base      : MSP as notified (Rs/qtl)
bonus         : bonus over and above MSP where announced (Rs/qtl); NULL = not verified
msp_effective : msp_base + bonus (bonus treated as 0 when not verified, flagged)
a2fl_cost     : CACP projected all-India A2+FL cost of production (Rs/qtl) where the release states it
"""
import pandas as pd
from .config import RAW, CURATED, PROC

SRC = {
    "OGD_2002_12": ("data.gov.in - Minimum Support Prices of crops (Rs/qtl), 2002-03 to 2012-13 "
                    "(file crops_price_msp.csv, mirrored from github.com/nitinvbharti/Agriculture_Analysis)",
                    "https://www.data.gov.in/"),
    "CMO_2012_16": ("Maharashtra CMO dataset - MSP table CMO_MSP_Mandi.csv (OGD hackathon release), "
                    "cross-checked against PIB 2013-14 column", "https://www.data.gov.in/"),
    "PIB_2013_vs_2024": ("PIB backgrounder 'A Consistent Increase in MSP' (Jun 2024)",
                         "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2024/jun/doc2024621343301.pdf"),
    "DES_KH_2016": ("DES / DA&FW - MSP for Kharif crops 2016-17 (with bonus)",
                    "https://desagri.gov.in/wp-content/uploads/2021/04/MSP-kharif-2016-17.pdf"),
    "PIB_RB_2016": ("PIB 15-Nov-2016 - Cabinet approves enhanced MSP for Rabi crops of 2016-17 (bonus for gram, masur, mustard, safflower)",
                    "https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=153642"),
    "PIB_KH_2018": ("PIB Aug-2018 - MSP for Kharif crops (2017-18 and 2018-19 with CACP cost)",
                    "https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=181467"),
    "PIB_KH_2019": ("PIB 03-Jul-2019 - Cabinet approves MSP for Kharif crops 2019-20",
                    "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1576844"),
    "PIB_KH_2020": ("PIB 01-Jun-2020 - MSP for Kharif crops 2020-21",
                    "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1628348"),
    "PIB_RB_2018": ("PIB Oct-2018 - MSP for Rabi crops of 2018-19 (RMS 2019-20)",
                    "https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=183926"),
    "PIB_RB_2019": ("PIB Oct-2019 - MSP for Rabi crops of 2019-20 (RMS 2020-21)",
                    "https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=193961"),
    "PIB_RB_2021": ("PIB Sep-2021 - MSP for Rabi crops RMS 2022-23",
                    "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2021/sep/doc202191311.pdf"),
    "PIB_ALL_2021_23": ("PIB - MSP table 2021-22 to 2023-24 (all mandated crops)",
                        "https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2003184"),
    "PIB_KH_2025": ("PIB May-2025 - Cabinet approves MSP for Kharif crops, marketing season 2025-26",
                    "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2131983"),
    "PIB_RB_2026": ("PIB Oct-2025 - Cabinet approves MSP for Rabi crops, RMS 2026-27 (also lists RMS 2025-26)",
                    "https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2173567"),
    "PIB_KH_2026": ("PIB 13-May-2026 - Cabinet approves MSP for Kharif crops, marketing season 2026-27",
                    "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2260617"),
    "NEWS_RB_2027": ("Business Standard 30-Sep-2026 - Cabinet hikes MSP for rabi crops, RMS 2027-28 (secondary; matches Global Agriculture report)",
                     "https://www.business-standard.com/economy/news/cabinet-rabi-msp-2027-28-wheat-safflower-mustard-126093000756_1.html"),
    "PIB_FRP_2018": ("PIB Jul-2018 - FRP of sugarcane for 2018-19 (Rs 275 at 10% recovery; 2017-18 Rs 255)",
                     "https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=1539078"),
    "PIB_JUTE_2019": ("PIB Mar-2019 - MSP raw jute 2019-20 Rs 3950 (2018-19 Rs 3700)",
                      "https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=1564328"),
    "NEWS_FRP_2019": ("Business Standard/PTI 24-Jul-2019 - Govt keeps sugarcane FRP unchanged at Rs 275/qtl for 2019-20 (secondary)",
                      "https://www.business-standard.com/article/pti-stories/govt-keeps-sugarcane-price-unchanged-at-rs-275-qtl-for-2019-20-119072401159_1.html"),
    "NEWS_JUTE_2018": ("Business Standard 25-Apr-2018 - raw jute MSP raised by Rs 200 to Rs 3,700 for 2018-19 (secondary; 2017-18 derived)",
                       "https://www.business-standard.com/amp/article/markets/govt-hikes-raw-jute-msp-by-rs-200-to-rs-3-700-quintal-for-2018-19-118042500449_1.html"),
}

SEASON = {"Paddy": "Kharif", "Jowar": "Kharif", "Bajra": "Kharif", "Ragi": "Kharif", "Maize": "Kharif",
          "Tur": "Kharif", "Moong": "Kharif", "Urad": "Kharif", "Groundnut": "Kharif",
          "Sunflower": "Kharif", "Soyabean": "Kharif", "Sesamum": "Kharif", "Nigerseed": "Kharif",
          "Cotton": "Kharif", "Wheat": "Rabi", "Barley": "Rabi", "Gram": "Rabi", "Masur": "Rabi",
          "Mustard": "Rabi", "Safflower": "Rabi", "Jute": "Other", "Sugarcane": "Other"}

VARIETY = {"Paddy": "Common", "Jowar": "Hybrid", "Cotton": "Medium staple (F-414/H-777 grade pre-2014)",
           "Soyabean": "Yellow", "Jute": "TD-5 / FAQ raw jute", "Sugarcane": "SMP (to 2008-09) / FRP (2009-10 on)",
           "Groundnut": "In shell"}

def main():
    rows = []


    def add(key, year, base, src, bonus=0.0, cost=None, note=""):
        rows.append(dict(msp_key=key, crop_year=year, msp_base=base, bonus=bonus, a2fl_cost=cost,
                         source_id=src, note=note))


    # --- A. data.gov.in 2002-2012 (parsed from file) --------------------------------------------------
    ogd = pd.read_csv(RAW / "crops_price_msp.csv")
    ogd.columns = [c.strip() for c in ogd.columns]
    name_map = {"Paddy (Common)": "Paddy", "Wheat": "Wheat", "Jowar (Hybrid)": "Jowar", "Bajra": "Bajra",
                "Ragi": "Ragi", "Maize": "Maize", "Barley": "Barley", "Gram": "Gram", "Masur": "Masur",
                "Arhar": "Tur", "Moong": "Moong", "Urad": "Urad",
                "Sugarcane (Statutory minimum price) a": "Sugarcane", "Cotton F-414/H-777": "Cotton",
                "Groundnut": "Groundnut", "Jute(TD-5)": "Jute", "Rapeseed/ mustard": "Mustard",
                "Sunflower": "Sunflower", "Soyabean (Yellow)": "Soyabean", "Safflower": "Safflower",
                "Sesamum": "Sesamum", "Niger seed": "Nigerseed"}
    first = ogd.columns[0]
    ogd[first] = ogd[first].str.strip()
    for _, r in ogd.iterrows():
        key = name_map.get(r[first])
        if not key:
            continue
        for y in ogd.columns[1:]:
            v = pd.to_numeric(r[y], errors="coerce")
            if pd.notna(v) and int(y) <= 2011:     # 2012 taken from CMO (identical values, cross-checked)
                add(key, int(y), float(v), "OGD_2002_12",
                    note="Bonus treatment as published by source (some years include bonus)")

    # --- B. CMO MSP table 2012-2016 (parsed) ------------------------------------------------------------
    cmo = pd.read_csv(RAW / "cmo_msp_mandi.csv")
    cmo_map = {"PADDY-UNHUSKED": "Paddy", "WHEAT(HUSKED)": "Wheat", "MAIZE": "Maize", "Jowar_Hybrid": "Jowar",
               "BAJRI": "Bajra", "Ragi_Maldandi": "Ragi", "BARLI": "Barley", "Gram_Yellow": "Gram",
               "Masur_Yellow": "Masur", "PIGEON PEA (TUR)": "Tur", "SPILT GERRN GRAM": "Moong",
               "SPLIT BLACK GRAM": "Urad", "GR.NUT KERNELS": "Groundnut", "MUSTARD": "Mustard",
               "SOYABEAN": "Soyabean", "SUNFLOWER": "Sunflower", "SESAMUM": "Sesamum", "NIGER-SEED": "Nigerseed",
               "SAFFLOWER": "Safflower", "COTTON": "Cotton", "Jute_Yellow": "Jute", "SUGAR-CANE": "Sugarcane",
               "SUGARCANE": "Sugarcane"}
    cmo["key"] = cmo["commodity"].map(cmo_map)
    cmo = cmo.dropna(subset=["key", "msprice"])
    for _, r in cmo.iterrows():
        y = int(r["year"])
        if 2012 <= y <= 2015 or (y == 2016 and r["key"] in ("Jute", "Sugarcane")):
            note = "Base MSP (excludes any bonus)"
            if r["key"] == "Groundnut":
                note += "; CMO label says 'kernels' but value equals groundnut-in-shell MSP"
            add(r["key"], y, float(r["msprice"]), "CMO_2012_16", note=note)

    # Bonus layer for crop year 2015 rabi (PIB relid=153642 '2015-16' column incl. bonus minus CMO base)
    BONUS_2015_RABI = {"Gram": 75, "Masur": 75}
    # Kharif 2015 pulses bonus (Rs 200) was announced but not verified from an official table here -> NULL
    for r in rows:
        if r["crop_year"] == 2015 and r["msp_key"] in BONUS_2015_RABI:
            r["bonus"] = BONUS_2015_RABI[r["msp_key"]]
            r["note"] += "; bonus from PIB relid=153642"
        if r["crop_year"] == 2015 and r["msp_key"] in ("Tur", "Moong", "Urad"):
            r["bonus"] = None
            r["note"] += "; kharif 2015-16 pulse bonus not verified -> left NULL"

    # --- C. Kharif 2016-17 (DES PDF, base + bonus) -------------------------------------------------------
    for k, base, bonus in [("Paddy", 1470, 0), ("Jowar", 1625, 0), ("Bajra", 1330, 0), ("Maize", 1365, 0),
                           ("Ragi", 1725, 0), ("Tur", 4625, 425), ("Moong", 4800, 425), ("Urad", 4575, 425),
                           ("Groundnut", 4120, 100), ("Soyabean", 2675, 100), ("Sunflower", 3850, 100),
                           ("Nigerseed", 3725, 100), ("Sesamum", 4800, 200), ("Cotton", 3860, 0)]:
        add(k, 2016, base, "DES_KH_2016", bonus=bonus)
    # --- D. Rabi 2016-17 (PIB) ------------------------------------------------------------------------
    for k, base, bonus in [("Wheat", 1625, 0), ("Barley", 1325, 0), ("Gram", 4000, 200), ("Masur", 3950, 150),
                           ("Mustard", 3700, 100), ("Safflower", 3700, 100)]:
        add(k, 2016, base, "PIB_RB_2016", bonus=bonus)

    # --- E/F/G. Kharif 2017, 2018 (relid 181467), 2019 (1576844), 2020 (1628348) with CACP A2+FL cost --
    KH = {  # key: [(year, msp, cost), ...]
        "Paddy":     [(2017, 1550, 1117), (2018, 1750, 1166), (2019, 1815, 1208), (2020, 1868, 1245)],
        "Jowar":     [(2017, 1700, 1556), (2018, 2430, 1619), (2019, 2550, 1698), (2020, 2620, 1746)],
        "Bajra":     [(2017, 1425, 949), (2018, 1950, 990), (2019, 2000, 1083), (2020, 2150, 1175)],
        "Maize":     [(2017, 1425, 1044), (2018, 1700, 1131), (2019, 1760, 1171), (2020, 1850, 1213)],
        "Ragi":      [(2017, 1900, 1861), (2018, 2897, 1931), (2019, 3150, 2100), (2020, 3295, 2194)],
        "Tur":       [(2017, 5450, 3318), (2018, 5675, 3432), (2019, 5800, 3636), (2020, 6000, 3796)],
        "Moong":     [(2017, 5575, 4286), (2018, 6975, 4650), (2019, 7050, 4699), (2020, 7196, 4797)],
        "Urad":      [(2017, 5400, 3265), (2018, 5600, 3438), (2019, 5700, 3477), (2020, 6000, 3660)],
        "Cotton":    [(2017, 4020, 3276), (2018, 5150, 3433), (2019, 5255, 3501), (2020, 5515, 3676)],
        "Groundnut": [(2017, 4450, 3159), (2018, 4890, 3260), (2019, 5090, 3394), (2020, 5275, 3515)],
        "Sunflower": [(2017, 4100, 3481), (2018, 5388, 3592), (2019, 5650, 3767), (2020, 5885, 3921)],
        "Soyabean":  [(2017, 3050, 2121), (2018, 3399, 2266), (2019, 3710, 2473), (2020, 3880, 2587)],
        "Sesamum":   [(2017, 5300, 4067), (2018, 6249, 4166), (2019, 6485, 4322), (2020, 6855, 4570)],
        "Nigerseed": [(2017, 4050, 3912), (2018, 5877, 3918), (2019, 5940, 3960), (2020, 6695, 4462)],
    }
    for k, lst in KH.items():
        for y, m, c in lst:
            src = {2017: "PIB_KH_2018", 2018: "PIB_KH_2018", 2019: "PIB_KH_2019", 2020: "PIB_KH_2020"}[y]
            add(k, y, m, src, cost=c, note="2017-18 pulse MSPs include bonus as stated in release" if (y == 2017 and k in ("Tur", "Moong", "Urad")) else "")

    # Rabi crop years 2017 (183926 prev col), 2018 (183926 + cost), 2019 (193961 + cost), 2020 (2021 doc)
    RB = {
        "Wheat":     [(2017, 1735, None), (2018, 1840, 866), (2019, 1925, 923), (2020, 1975, 960)],
        "Barley":    [(2017, 1410, None), (2018, 1440, 860), (2019, 1525, 919), (2020, 1600, 971)],
        "Gram":      [(2017, 4400, None), (2018, 4620, 2637), (2019, 4875, 2801), (2020, 5100, 2866)],
        "Masur":     [(2017, 4250, None), (2018, 4475, 2532), (2019, 4800, 2727), (2020, 5100, 2864)],
        "Mustard":   [(2017, 4000, None), (2018, 4200, 2212), (2019, 4425, 2323), (2020, 4650, 2415)],
        "Safflower": [(2017, 4100, None), (2018, 4945, 3294), (2019, 5215, 3470), (2020, 5327, 3551)],
    }
    for k, lst in RB.items():
        for y, m, c in lst:
            src = {2017: "PIB_RB_2018", 2018: "PIB_RB_2018", 2019: "PIB_RB_2019", 2020: "PIB_RB_2021"}[y]
            add(k, y, m, src, cost=c)

    # --- Crop years 2021-2023 (PIB PRID=2003184, labelled by crop year) ---------------------------------
    ALL_21_23 = {"Paddy": (1940, 2040, 2183), "Jowar": (2738, 2970, 3180), "Bajra": (2250, 2350, 2500),
                 "Ragi": (3377, 3578, 3846), "Maize": (1870, 1962, 2090), "Tur": (6300, 6600, 7000),
                 "Moong": (7275, 7755, 8558), "Urad": (6300, 6600, 6950), "Groundnut": (5550, 5850, 6377),
                 "Sunflower": (6015, 6400, 6760), "Soyabean": (3950, 4300, 4600), "Sesamum": (7307, 7830, 8635),
                 "Nigerseed": (6930, 7287, 7734), "Cotton": (5726, 6080, 6620), "Wheat": (2015, 2125, 2275),
                 "Barley": (1635, 1735, 1850), "Gram": (5230, 5335, 5440), "Masur": (5500, 6000, 6425),
                 "Mustard": (5050, 5450, 5650), "Safflower": (5441, 5650, 5800), "Jute": (4500, 4750, 5050)}
    for k, vals in ALL_21_23.items():
        for y, m in zip((2021, 2022, 2023), vals):
            add(k, y, m, "PIB_ALL_2021_23")
    # Kharif crop year 2024 (KMS 2024-25) with CACP cost; rabi crop year 2023 cost (RMS 2024-25)
    KH24 = {"Paddy": (2300, 1533), "Jowar": (3371, 2247), "Bajra": (2625, 1485), "Ragi": (4290, 2860),
            "Maize": (2225, 1447), "Tur": (7550, 4761), "Moong": (8682, 5788), "Urad": (7400, 4883),
            "Groundnut": (6783, 4522), "Sunflower": (7280, 4853), "Soyabean": (4892, 3261),
            "Sesamum": (9267, 6178), "Nigerseed": (8717, 5811), "Cotton": (7121, 4747)}
    for k, (m, c) in KH24.items():
        add(k, 2024, m, "PIB_2013_vs_2024", cost=c)
    for r in rows:
        if r["crop_year"] == 2023 and r["msp_key"] in {"Wheat": 1, "Barley": 1, "Gram": 1, "Masur": 1, "Mustard": 1, "Safflower": 1}:
            r["a2fl_cost"] = {"Wheat": 1128, "Barley": 1158, "Gram": 3400, "Masur": 3405, "Mustard": 2855, "Safflower": 3807}[r["msp_key"]]
            r["note"] = "A2+FL cost from PIB Jun-2024 backgrounder (RMS 2024-25)"

    # --- Kharif crop year 2025 (KMS 2025-26) and rabi crop years 2024/2025 (RMS 2025-26 / 2026-27) ---
    KH25 = {"Paddy": (2369, 1579), "Jowar": (3699, 2466), "Bajra": (2775, 1703), "Ragi": (4886, 3257),
            "Maize": (2400, 1508), "Tur": (8000, 5038), "Moong": (8768, 5845), "Urad": (7800, 5114),
            "Groundnut": (7263, 4842), "Sunflower": (7721, 5147), "Soyabean": (5328, 3552),
            "Sesamum": (9846, 6564), "Nigerseed": (9537, 6358), "Cotton": (7710, 5140)}
    for k, (m, c) in KH25.items():
        add(k, 2025, m, "PIB_KH_2025", cost=c)
    RB = {"Wheat": (2425, 2585, 1239), "Barley": (1980, 2150, 1361), "Gram": (5650, 5875, 3699),
          "Masur": (6700, 7000, 3705), "Mustard": (5950, 6200, 3210), "Safflower": (5940, 6540, 4360)}
    for k, (m24, m25, c25) in RB.items():
        add(k, 2024, m24, "PIB_RB_2026")
        add(k, 2025, m25, "PIB_RB_2026", cost=c25)

    # --- 2026 season: Kharif crop year 2026 (KMS 2026-27, PIB 13-May-2026) with CACP A2+FL cost ---
    KH26 = {"Paddy": (2441, 1627), "Jowar": (4023, 2682), "Bajra": (2900, 1858), "Ragi": (5205, 3470),
            "Maize": (2410, 1544), "Tur": (8450, 5496), "Moong": (8780, 5438), "Urad": (8200, 5418),
            "Groundnut": (7517, 5011), "Sunflower": (8343, 5562), "Soyabean": (5708, 3805),
            "Sesamum": (10346, 6897), "Nigerseed": (10052, 6701), "Cotton": (8267, 5511)}
    for k, (m, c) in KH26.items():
        add(k, 2026, m, "PIB_KH_2026", cost=c)
    # Rabi crop year 2026 (RMS 2027-28, CCEA 30-Sep-2026). Only margins over cost were reported,
    # so the cost is left NULL rather than back-calculated.
    RB26 = {"Wheat": 2610, "Barley": 2286, "Gram": 5958, "Masur": 7390, "Mustard": 6613, "Safflower": 7215}
    for k, m in RB26.items():
        add(k, 2026, m, "NEWS_RB_2027", note="RMS 2027-28 announced 30-Sep-2026; secondary source, two outlets agree")

    # --- Sugarcane FRP & Jute 2017-2019 ------------------------------------------------------------------
    add("Sugarcane", 2017, 255, "PIB_FRP_2018", note="FRP at 9.5% basic recovery")
    add("Sugarcane", 2018, 275, "PIB_FRP_2018", note="FRP at 10% basic recovery")
    add("Sugarcane", 2019, 275, "NEWS_FRP_2019", note="FRP 2019-20 reported unchanged at Rs 275 (secondary source)")
    add("Jute", 2018, 3700, "PIB_JUTE_2019")
    add("Jute", 2019, 3950, "PIB_JUTE_2019")
    add("Jute", 2017, 3500, "NEWS_JUTE_2018", note="Derived: 2018-19 MSP of Rs 3700 was a Rs 200 increase")
    rows[:] = [r for r in rows if r["msp_base"] is not None]

    msp = pd.DataFrame(rows)
    # de-duplicate (prefer later, more specific sources): keep last
    msp = msp.drop_duplicates(["msp_key", "crop_year"], keep="last")
    msp["bonus_verified"] = msp["bonus"].notna()
    msp["msp_effective"] = msp["msp_base"] + msp["bonus"].fillna(0)
    msp["season"] = msp["msp_key"].map(SEASON)
    msp["variety"] = msp["msp_key"].map(VARIETY).fillna("FAQ")
    msp["crop_year_label"] = msp["crop_year"].astype(str) + "-" + (msp["crop_year"] + 1).astype(str).str[-2:]
    msp["marketing_season"] = msp.apply(
        lambda r: ("RMS " + f"{r.crop_year+1}-{str(r.crop_year+2)[-2:]}") if r.season == "Rabi"
        else ("KMS " + r.crop_year_label if r.season == "Kharif" else r.crop_year_label), axis=1)
    msp["source_title"] = msp["source_id"].map(lambda s: SRC[s][0])
    msp["source_url"] = msp["source_id"].map(lambda s: SRC[s][1])
    msp["verification"] = msp["source_id"].map(lambda s: "secondary" if s.startswith("NEWS") else "official")
    msp["msp_over_a2fl_pct"] = (msp["msp_effective"] / msp["a2fl_cost"] - 1) * 100
    msp = msp.sort_values(["msp_key", "crop_year"]).reset_index(drop=True)

    # Cross-check: CMO 2013 vs PIB 2013-14 column
    PIB_2013 = {"Paddy": 1310, "Jowar": 1500, "Bajra": 1250, "Ragi": 1500, "Maize": 1310, "Tur": 4300,
                "Moong": 4500, "Urad": 4300, "Groundnut": 4000, "Sunflower": 3700, "Soyabean": 2560,
                "Sesamum": 2500, "Nigerseed": 3500, "Cotton": 3700, "Wheat": 1400, "Barley": 1100,
                "Gram": 3100, "Masur": 2950, "Mustard": 3050, "Safflower": 3000}
    chk = msp[msp.crop_year == 2013].set_index("msp_key")["msp_base"]
    xcheck = pd.DataFrame({"cmo_2013": chk, "pib_2013": pd.Series(PIB_2013)}).dropna()
    xcheck["match"] = xcheck.cmo_2013 == xcheck.pib_2013
    RESOLUTION = {
        "Bajra": ("use PIB 1250", "CMO 1310 equals the maize MSP (copy error in CMO); 2012-13=1175, 2014-15=1250"),
        "Sesamum": ("keep CMO 4500", "PIB value 2500 breaks the series 4200 (2012) -> 4600 (2014); likely typo"),
    }
    xcheck["resolution"] = [RESOLUTION.get(k, ("match", ""))[0] for k in xcheck.index]
    xcheck["reason"] = [RESOLUTION.get(k, ("", ""))[1] for k in xcheck.index]
    xcheck.index.name = "msp_key"
    xcheck.to_csv(PROC / "dq_msp_crosscheck_2013.csv")
    _m = (msp.msp_key == "Bajra") & (msp.crop_year == 2013)
    msp.loc[_m, ["msp_base", "msp_effective", "source_id"]] = [1250.0, 1250.0, "PIB_2013_vs_2024"]
    msp.loc[_m, "source_title"] = SRC["PIB_2013_vs_2024"][0]
    msp.loc[_m, "source_url"] = SRC["PIB_2013_vs_2024"][1]
    msp.loc[_m, "note"] = "CMO value 1310 rejected (equals maize MSP); PIB 2013-14 value used"

    pd.DataFrame([{"source_id": k, "title": v[0], "url": v[1]} for k, v in SRC.items()]).to_csv(
        CURATED / "msp_sources.csv", index=False)
    msp.to_csv(CURATED / "msp_official_curated.csv", index=False)
    print(len(msp), "MSP rows")
    return msp


if __name__ == "__main__":
    main()
