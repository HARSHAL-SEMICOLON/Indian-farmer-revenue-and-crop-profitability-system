"""
Central configuration: paths, crop registry (units + conversions), geography mappings.

Every conversion factor here is an explicit, documented assumption. See docs/METHODOLOGY.md.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CURATED = ROOT / "data" / "curated"        # hand-transcribed official tables (with citations)
PROC = ROOT / "data" / "processed"
EXPORT = ROOT / "power_bi" / "data"
DB_PATH = ROOT / "database" / "indian_agri_revenue.db"
RESULTS = ROOT / "outputs" / "results"
FIGURES = ROOT / "outputs" / "figures"
SQL_DIR = ROOT / "sql"

for _d in (CURATED, PROC, EXPORT, DB_PATH.parent, RESULTS, FIGURES):
    _d.mkdir(parents=True, exist_ok=True)

HA_PER_ACRE = 0.404686          # 1 acre = 0.404686 ha
ACRES_PER_HA = 1 / HA_PER_ACRE  # 2.47105

# Analysis windows
MSP_VALUATION_YEARS = list(range(2004, 2027))   # crop years with a complete official MSP series (valued where production exists)
PROVISIONAL_YEARS = {2019}                      # district totals diverge from DES 3rd AE 2019-20 (see DQ)
COST_YEARS = list(range(2008, 2014))            # DES cost-of-cultivation coverage (2008-09 .. 2013-14)
RAINFALL_LAST_YEAR = 2015                       # IMD subdivision series ends 2015

# Paddy out-turn: FCI/GoI standard out-turn ratio for raw rice = 67% (1 qtl paddy -> 0.67 qtl rice)
RICE_TO_PADDY = 1 / 0.67
# Cotton: APY reports LINT in bales of 170 kg; MSP is for KAPAS (seed cotton).
# Ginning out-turn (lint share of kapas) assumed 34% (typical Indian range 33-36%).
COTTON_GOT = 0.34
COTTON_BALE_KG = 170
JUTE_BALE_KG = 180

# ---------------------------------------------------------------------------------------------
# Crop registry. apy_name = name in the DES APY district file. msp_key = key in fact_msp.
# to_msp_qtl = multiply APY production (in apy_unit) by this to get quintals in the SAME
#              commodity form that MSP / mandi prices are quoted in.
# ---------------------------------------------------------------------------------------------
CROPS = [
    # crop_name,          apy_name,             group,          season,      apy_unit,         msp_form,                  to_msp_qtl,                                  msp_key
    ("Rice",              "Rice",               "Cereals",      "Kharif",    "tonnes (milled rice)", "Paddy (common), Rs/qtl", 10 * RICE_TO_PADDY,                     "Paddy"),
    ("Wheat",             "Wheat",              "Cereals",      "Rabi",      "tonnes",         "Wheat grain",             10.0,                                        "Wheat"),
    ("Maize",             "Maize",              "Cereals",      "Kharif",    "tonnes",         "Maize grain",             10.0,                                        "Maize"),
    ("Jowar",             "Jowar",              "Coarse cereals", "Kharif",  "tonnes",         "Jowar hybrid",            10.0,                                        "Jowar"),
    ("Bajra",             "Bajra",              "Coarse cereals", "Kharif",  "tonnes",         "Bajra",                   10.0,                                        "Bajra"),
    ("Ragi",              "Ragi",               "Coarse cereals", "Kharif",  "tonnes",         "Ragi",                    10.0,                                        "Ragi"),
    ("Barley",            "Barley",             "Coarse cereals", "Rabi",    "tonnes",         "Barley",                  10.0,                                        "Barley"),
    ("Gram",              "Gram",               "Pulses",       "Rabi",      "tonnes",         "Gram (whole)",            10.0,                                        "Gram"),
    ("Arhar/Tur",         "Arhar/Tur",          "Pulses",       "Kharif",    "tonnes",         "Tur (whole)",             10.0,                                        "Tur"),
    ("Moong",             "Moong(Green Gram)",  "Pulses",       "Kharif",    "tonnes",         "Moong (whole)",           10.0,                                        "Moong"),
    ("Urad",              "Urad",               "Pulses",       "Kharif",    "tonnes",         "Urad (whole)",            10.0,                                        "Urad"),
    ("Masoor",            "Masoor",             "Pulses",       "Rabi",      "tonnes",         "Masur (whole)",           10.0,                                        "Masur"),
    ("Groundnut",         "Groundnut",          "Oilseeds",     "Kharif",    "tonnes (in pods)", "Groundnut in shell",     10.0,                                        "Groundnut"),
    ("Rapeseed & Mustard", "Rapeseed &Mustard", "Oilseeds",     "Rabi",      "tonnes",         "Rapeseed & mustard seed", 10.0,                                        "Mustard"),
    ("Soyabean",          "Soyabean",           "Oilseeds",     "Kharif",    "tonnes",         "Soyabean (yellow)",       10.0,                                        "Soyabean"),
    ("Sunflower",         "Sunflower",          "Oilseeds",     "Kharif",    "tonnes",         "Sunflower seed",          10.0,                                        "Sunflower"),
    ("Sesamum",           "Sesamum",            "Oilseeds",     "Kharif",    "tonnes",         "Sesamum",                 10.0,                                        "Sesamum"),
    ("Nigerseed",         "Niger Seed",         "Oilseeds",     "Kharif",    "tonnes",         "Nigerseed",               10.0,                                        "Nigerseed"),
    ("Safflower",         "Safflower",          "Oilseeds",     "Rabi",      "tonnes",         "Safflower",               10.0,                                        "Safflower"),
    ("Cotton",            "Cotton(Lint)",       "Fibres",       "Kharif",    "bales of 170 kg (lint)", "Kapas (seed cotton), medium staple", COTTON_BALE_KG / 100 / COTTON_GOT, "Cotton"),
    ("Jute",              "Jute",               "Fibres",       "Kharif",    "bales of 180 kg", "Raw jute",               JUTE_BALE_KG / 100,                          "Jute"),
    ("Sugarcane",         "Sugarcane",          "Cash crops",   "Whole Year", "tonnes (cane)", "Sugarcane (FRP/SMP)",     10.0,                                        "Sugarcane"),
    # Non-MSP crops: production analysed; priced only where a mandi series exists (MH 2014-16)
    ("Onion",             "Onion",              "Horticulture", "Whole Year", "tonnes",        None,                      10.0,                                        None),
    ("Potato",            "Potato",             "Horticulture", "Rabi",      "tonnes",         None,                      10.0,                                        None),
    ("Dry Chillies",      "Dry Chillies",       "Spices",       "Whole Year", "tonnes",        None,                      10.0,                                        None),
    ("Turmeric",          "Turmeric",           "Spices",       "Whole Year", "tonnes",        None,                      10.0,                                        None),
]
CROP_COLS = ["crop_name", "apy_name", "crop_group", "primary_season", "apy_unit", "price_form",
             "to_price_qtl_factor", "msp_key"]

# Normalise state names across sources -------------------------------------------------------
STATE_ALIASES = {
    "Andaman and Nicobar Island": "Andaman and Nicobar Islands",
    "Andaman and Nicobar": "Andaman and Nicobar Islands",
    "The Dadra And Nagar Haveli": "Dadra and Nagar Haveli",
    "Jammu and Kashmir ": "Jammu and Kashmir",
    "Telangana ": "Telangana",
    "Orissa": "Odisha",
    "Pondicherry": "Puducherry",
    "Uttrakhand": "Uttarakhand",
    "NCT of Delhi": "Delhi",
    "Chattisgarh": "Chhattisgarh",
    "Keralam": "Kerala",
}

# IMD meteorological subdivisions belonging to each state. Where a state has several
# subdivisions its state rainfall = simple mean of them (documented approximation; no
# area weights are available in the source).
STATE_TO_SUBDIVISIONS = {
    "Andaman and Nicobar Islands": ["ANDAMAN & NICOBAR ISLANDS"],
    "Arunachal Pradesh": ["ARUNACHAL PRADESH"],
    "Assam": ["ASSAM & MEGHALAYA"],
    "Meghalaya": ["ASSAM & MEGHALAYA"],
    "Nagaland": ["NAGA MANI MIZO TRIPURA"],
    "Manipur": ["NAGA MANI MIZO TRIPURA"],
    "Mizoram": ["NAGA MANI MIZO TRIPURA"],
    "Tripura": ["NAGA MANI MIZO TRIPURA"],
    "Sikkim": ["SUB HIMALAYAN WEST BENGAL & SIKKIM"],
    "West Bengal": ["SUB HIMALAYAN WEST BENGAL & SIKKIM", "GANGETIC WEST BENGAL"],
    "Odisha": ["ORISSA"],
    "Jharkhand": ["JHARKHAND"],
    "Bihar": ["BIHAR"],
    "Uttar Pradesh": ["EAST UTTAR PRADESH", "WEST UTTAR PRADESH"],
    "Uttarakhand": ["UTTARAKHAND"],
    "Haryana": ["HARYANA DELHI & CHANDIGARH"],
    "Delhi": ["HARYANA DELHI & CHANDIGARH"],
    "Chandigarh": ["HARYANA DELHI & CHANDIGARH"],
    "Punjab": ["PUNJAB"],
    "Himachal Pradesh": ["HIMACHAL PRADESH"],
    "Jammu and Kashmir": ["JAMMU & KASHMIR"],
    "Rajasthan": ["WEST RAJASTHAN", "EAST RAJASTHAN"],
    "Madhya Pradesh": ["WEST MADHYA PRADESH", "EAST MADHYA PRADESH"],
    "Gujarat": ["GUJARAT REGION", "SAURASHTRA & KUTCH"],
    "Dadra and Nagar Haveli": ["GUJARAT REGION"],
    "Daman and Diu": ["SAURASHTRA & KUTCH"],
    "Goa": ["KONKAN & GOA"],
    "Maharashtra": ["KONKAN & GOA", "MADHYA MAHARASHTRA", "MATATHWADA", "VIDARBHA"],
    "Chhattisgarh": ["CHHATTISGARH"],
    "Andhra Pradesh": ["COASTAL ANDHRA PRADESH", "RAYALSEEMA"],
    "Telangana": ["TELANGANA"],
    "Tamil Nadu": ["TAMIL NADU"],
    "Puducherry": ["TAMIL NADU"],
    "Karnataka": ["COASTAL KARNATAKA", "NORTH INTERIOR KARNATAKA", "SOUTH INTERIOR KARNATAKA"],
    "Kerala": ["KERALA"],
}

# Broad regions for slicing
STATE_REGION = {
    "Punjab": "North", "Haryana": "North", "Himachal Pradesh": "North", "Jammu and Kashmir": "North",
    "Uttarakhand": "North", "Uttar Pradesh": "North", "Delhi": "North", "Chandigarh": "North", "Ladakh": "North",
    "Rajasthan": "West", "Gujarat": "West", "Maharashtra": "West", "Goa": "West",
    "Dadra and Nagar Haveli": "West", "Daman and Diu": "West",
    "Madhya Pradesh": "Central", "Chhattisgarh": "Central",
    "Bihar": "East", "Jharkhand": "East", "Odisha": "East", "West Bengal": "East",
    "Andaman and Nicobar Islands": "East",
    "Assam": "North-East", "Arunachal Pradesh": "North-East", "Meghalaya": "North-East",
    "Manipur": "North-East", "Mizoram": "North-East", "Nagaland": "North-East", "Tripura": "North-East",
    "Sikkim": "North-East",
    "Andhra Pradesh": "South", "Telangana": "South", "Karnataka": "South", "Kerala": "South",
    "Tamil Nadu": "South", "Puducherry": "South",
}


def connect_ro():
    """Read-only, lock-free connection (works on network / VM-mounted folders too)."""
    import sqlite3
    return sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)


def norm_state(s):
    if s is None:
        return s
    s = str(s).strip()
    return STATE_ALIASES.get(s, s)


def cpi_deflator_2018():
    """Crop year Y -> CPI deflator (2018-19 = 100), using the mean CPI of calendar years Y and Y+1.
    Available only where both calendar years exist in the World Bank series (currently to crop year 2024)."""
    import pandas as pd
    cpi = pd.read_csv(RAW / "cpi_india_worldbank.csv").set_index("year")["cpi_2010_100"]
    defl = {y: (cpi[y] + cpi[y + 1]) / 2 for y in cpi.index if (y + 1) in cpi.index}
    return {y: v / defl[2018] * 100 for y, v in defl.items()}
