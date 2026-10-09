"""
Generate a Power BI Project (PBIP: TMDL semantic model + PBIR report) from power_bi/data/.
Run:  python power_bi/build_pbip.py   -> power_bi/pbip/FarmerRevenueIntelligence.pbip
Open the .pbip in Power BI Desktop (preview features 'Power BI Project', TMDL and PBIR enabled), then Refresh.
"""
import json
import re
import shutil
import uuid
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "power_bi" / "data"
OUT = ROOT / "power_bi" / "pbip"
NAME = "FarmerRevenueIntelligence"
WIN_EXPORT = r"E:\DA PROJECTS\Indian Farmer Revenue Intelligence\power_bi\data" + "\\"

TABLES = ["dim_crop", "dim_state", "dim_location", "dim_year", "dim_market", "dim_date",
          "fact_production", "fact_district_crop_year", "fact_state_crop_year", "fact_msp", "fact_market_price",
          "fact_cost_of_cultivation", "fact_weather_state", "dq_issues", "dq_validation", "dq_coverage", "ref_sources",
          "agg_q04b_value_growth_decomposition", "agg_q07a_rain_yield_association",
          "agg_q10a_market_volatility_mh", "agg_q05a_cross_market_dispersion_2024",
          "agg_q11b_msp_gap_by_month_2026", "agg_q11c_dispersion_2026", "agg_q11f_daily_median_price_2026",
          "agg_q11g_season_2026_outlook", "agg_q11h_msp_2026_27_vs_cost"]

RELS = [("fact_production.location_id", "dim_location.location_id"), ("fact_production.crop_id", "dim_crop.crop_id"),
        ("fact_production.crop_year", "dim_year.crop_year"),
        ("fact_district_crop_year.location_id", "dim_location.location_id"),
        ("fact_district_crop_year.crop_id", "dim_crop.crop_id"), ("fact_district_crop_year.crop_year", "dim_year.crop_year"),
        ("dim_location.state_id", "dim_state.state_id"),
        ("fact_state_crop_year.state_id", "dim_state.state_id"), ("fact_state_crop_year.crop_id", "dim_crop.crop_id"),
        ("fact_state_crop_year.crop_year", "dim_year.crop_year"),
        ("fact_msp.crop_id", "dim_crop.crop_id"), ("fact_msp.crop_year", "dim_year.crop_year"),
        ("fact_market_price.market_id", "dim_market.market_id"), ("fact_market_price.crop_id", "dim_crop.crop_id"),
        ("fact_market_price.date_key", "dim_date.date_key"), ("dim_market.state_id", "dim_state.state_id"),
        ("fact_cost_of_cultivation.crop_id", "dim_crop.crop_id"), ("fact_cost_of_cultivation.state_id", "dim_state.state_id"),
        ("fact_cost_of_cultivation.crop_year", "dim_year.crop_year"),
        ("fact_weather_state.state_id", "dim_state.state_id"), ("fact_weather_state.crop_year", "dim_year.crop_year")]

SORT_BY = {("dim_date", "month_name"): "month", ("fact_market_price", "msp_price_band"): "msp_price_band_order", ("dim_year", "crop_year_label"): "crop_year"}
DATA_CAT = {("dim_state", "state_name"): "StateOrProvince"}


def gid():
    return str(uuid.uuid4())


def q(name):  # TMDL identifier quoting
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else "'" + name.replace("'", "''") + "'"


def is_key(col):
    return col.endswith("_id") or col.endswith("_key") or col in ("crop_year", "year", "month", "agri_year")


# ------------------------------------------------------------------ semantic model
def column_types(table):
    df = pd.read_csv(EXPORT / f"{table}.csv", low_memory=False)
    out = []
    for c in df.columns:
        s = df[c]
        if c == "price_date":
            out.append((c, "dateTime", "type date"))
        elif is_key(c) and pd.api.types.is_numeric_dtype(s):
            out.append((c, "int64", "Int64.Type"))
        elif pd.api.types.is_integer_dtype(s):
            out.append((c, "int64", "Int64.Type"))
        elif pd.api.types.is_numeric_dtype(s):
            out.append((c, "double", "type number"))
        else:
            out.append((c, "string", "type text"))
    return out


def table_tmdl(table):
    cols = column_types(table)
    L = [f"table {q(table)}", f"\tlineageTag: {gid()}", ""]
    for c, dt, _ in cols:
        L.append(f"\tcolumn {q(c)}")
        L.append(f"\t\tdataType: {dt}")
        if dt == "int64":
            L.append("\t\tformatString: 0")
        elif dt == "double":
            L.append("\t\tformatString: #,0.00")
        elif dt == "dateTime":
            L.append("\t\tformatString: dd-mmm-yyyy")
        if is_key(c) and c not in ("crop_year", "year", "month"):
            L.append("\t\tisHidden")
        if (table, c) in DATA_CAT:
            L.append(f"\t\tdataCategory: {DATA_CAT[(table, c)]}")
        L.append(f"\t\tlineageTag: {gid()}")
        L.append("\t\tsummarizeBy: none" if (dt != "double" or is_key(c)) else "\t\tsummarizeBy: sum")
        L.append(f"\t\tsourceColumn: {c}")
        if (table, c) in SORT_BY:
            L.append(f"\t\tsortByColumn: {SORT_BY[(table, c)]}")
        L.append("")
        L.append("\t\tannotation SummarizationSetBy = Automatic")
        L.append("")
    types = ", ".join('{"%s", %s}' % (c, m) for c, _, m in cols)
    m = [
        "let",
        f'    Source = Csv.Document(File.Contents(ExportFolder & "{table}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        '    Nulls = Table.TransformColumns(Promoted, List.Transform(Table.ColumnNames(Promoted), (c) => {c, each if _ = "" then null else _})),',
        f'    Typed = Table.TransformColumnTypes(Nulls, {{{types}}}, "en-US")',
        "in",
        "    Typed"]
    L.append(f"\tpartition {q(table)} = m")
    L.append("\t\tmode: import")
    L.append("\t\tsource =")
    L += ["\t\t\t\t" + x for x in m]
    L.append("")
    L.append("\tannotation PBI_ResultType = Table")
    L.append("")
    return "\n".join(L)


def fmt_for(name):
    if any(k in name for k in ("Label", "Flag", "Disclaimer", "Unit", "Available", "Color")):
        return None
    if "%" in name:
        return "0.0%"
    if "(r)" in name:
        return "0.00"
    if name in ("First Year", "Last Year"):
        return "0"
    if "(M ha)" in name or "(M t" in name or "lakh" in name:
        return "#,0.00"
    return "#,0"


def parse_measures():
    text = (ROOT / "power_bi" / "dax_measures.dax").read_text(encoding="utf-8")
    measures, folder, cur = [], "General", None
    for raw in text.splitlines():
        line = raw.rstrip()
        mf = re.match(r"// -+ Folder: (.+?) -+", line)
        if mf:
            folder = mf.group(1).strip()
            continue
        if line.strip().startswith("//") or not line.strip():
            continue
        head = re.match(r"^([A-Za-z][^=]*?) = ?(.*)$", line)
        cur_open = cur is not None and ("\n".join(cur["expr"]).count("(") != "\n".join(cur["expr"]).count(")") or not cur["expr"])
        if head and not cur_open and "[" not in head.group(1) and not line.startswith((" ", "\t")) \
                and not re.match(r"^(VAR|RETURN)\b", line):
            cur = {"name": head.group(1).strip(), "expr": [head.group(2)] if head.group(2) else [], "folder": folder}
            measures.append(cur)
        elif cur:
            cur["expr"].append(line)
    return measures


def measures_tmdl():
    L = ["table _Measures", f"\tlineageTag: {gid()}", ""]
    for m in parse_measures():
        L.append(f"\tmeasure {q(m['name'])} =")
        for e in m["expr"]:
            L.append("\t\t\t" + e)
        f = fmt_for(m["name"])
        if f:
            L.append(f"\t\tformatString: {f}")
        L.append(f"\t\tdisplayFolder: {m['folder']}")
        L.append(f"\t\tlineageTag: {gid()}")
        L.append("")
    L += ["\tcolumn Value", "\t\tdataType: string", "\t\tisHidden", f"\t\tlineageTag: {gid()}",
          "\t\tsummarizeBy: none", "\t\tisNameInferred", "\t\tsourceColumn: [Value]", "",
          "\t\tannotation SummarizationSetBy = Automatic", "",
          "\tpartition _Measures = calculated", "\t\tmode: import", '\t\tsource = ROW("Value", "measures")', "",
          "\tannotation PBI_Id = " + uuid.uuid4().hex, ""]
    return "\n".join(L)


def build_model(sm):
    d = sm / "definition"
    (d / "tables").mkdir(parents=True)
    (sm / "definition.pbism").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}}, indent=2))
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1600\n\n")
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tsourceQueryCulture: en-US", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
             "annotation PBI_QueryOrder = " + json.dumps(["ExportFolder"] + TABLES), "",
             "annotation __PBI_TimeIntelligenceEnabled = 0", ""]
    for t in ["_Measures"] + TABLES:
        model.append(f"ref table {q(t)}")
    (d / "model.tmdl").write_text("\n".join(model) + "\n")
    (d / "expressions.tmdl").write_text(
        f'expression ExportFolder = "{WIN_EXPORT}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {gid()}\n\n\tannotation PBI_ResultType = Text\n\n\tannotation PBI_NavigationStepName = Navigation\n")
    for t in TABLES:
        (d / "tables" / f"{t}.tmdl").write_text(table_tmdl(t), encoding="utf-8")
    (d / "tables" / "_Measures.tmdl").write_text(measures_tmdl(), encoding="utf-8")
    rel = []
    for f, t in RELS:
        rel += [f"relationship {gid()}", f"\tfromColumn: {f}", f"\ttoColumn: {t}", ""]
    (d / "relationships.tmdl").write_text("\n".join(rel))


# ------------------------------------------------------------------ report (PBIR)
SCH = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
BASE_THEME = "Fluent2-CY26SU09"   # copied from a report saved by the user's Power BI Desktop (Sep 2026)


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def col(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def meas(prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": prop}}


def agg(entity, prop, fn=0):  # 0 sum, 1 avg
    return {"Aggregation": {"Expression": col(entity, prop), "Function": fn}}


def proj(field):
    if "Measure" in field:
        ref = "_Measures." + field["Measure"]["Property"]
        native = field["Measure"]["Property"]
    elif "Aggregation" in field:
        c = field["Aggregation"]["Expression"]["Column"]
        fn = {0: "Sum", 1: "Avg"}[field["Aggregation"]["Function"]]
        ref = f"{fn}({c['Expression']['SourceRef']['Entity']}.{c['Property']})"
        native = f"{fn} of {c['Property']}"
    else:
        ref = field["Column"]["Expression"]["SourceRef"]["Entity"] + "." + field["Column"]["Property"]
        native = field["Column"]["Property"]
    return {"field": field, "queryRef": ref, "nativeQueryRef": native}


def where_cond(entity, prop, kind, value, alias="t"):
    return {"Condition": {"Comparison": {"ComparisonKind": kind,
            "Left": {"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": prop}},
            "Right": {"Literal": {"Value": value}}}}}


def range_filter(entity, prop, lo, hi, name):
    a = where_cond(entity, prop, 2, f"{lo}L")["Condition"]
    b = where_cond(entity, prop, 4, f"{hi}L")["Condition"]
    return {"name": name, "field": col(entity, prop), "type": "Advanced",
            "filter": {"Version": 2, "From": [{"Name": "t", "Entity": entity, "Type": 0}],
                       "Where": [{"Condition": {"And": {"Left": a, "Right": b}}}]}}


def in_filter_expr(entity, prop, values):
    return {"Version": 2, "From": [{"Name": "t", "Entity": entity, "Type": 0}],
            "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": prop}}],
                                            "Values": [[{"Literal": {"Value": v}}] for v in values]}}}]}


def in_filter(entity, prop, values, name):
    return {"name": name, "field": col(entity, prop), "type": "Categorical", "filter": in_filter_expr(entity, prop, values)}


def measure_min_filter(prop, minimum, name):
    return {"name": name, "field": meas(prop), "type": "Advanced",
            "filter": {"Version": 2, "From": [{"Name": "m", "Entity": "_Measures", "Type": 0}],
                       "Where": [{"Condition": {"Comparison": {"ComparisonKind": 2,
                                  "Left": {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": prop}},
                                  "Right": {"Literal": {"Value": f"{minimum}D"}}}}}]}}


def cf_color(target_measure, color_measure):
    """Field-value conditional formatting: font colour of one table column comes from a colour measure."""
    return {"properties": {"fontColor": {"solid": {"color": {"expr": meas(color_measure)}}}},
            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": "_Measures." + target_measure}}


class Page:
    def __init__(self, pid, display, filters=None):
        self.pid, self.display, self.visuals, self.filters, self.interactions = pid, display, [], filters or [], []
        self.z = 0

    def add(self, vname, vtype, x, y, w, h, roles=None, title=None, objects=None, filters=None, sort=None, extra_vco=None):
        self.z += 1
        visual = {"visualType": vtype, "drillFilterOtherVisuals": True}
        if roles:
            qs = {r: {"projections": [proj(f) for f in fs]} for r, fs in roles.items()}
            visual["query"] = {"queryState": qs}
            if sort:
                visual["query"]["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}], "isDefaultSort": True}
        if objects:
            visual["objects"] = objects
        if vtype == "tableEx":
            objects = {"total": [{"properties": {"totals": lit("false")}}], **(objects or {})}
            visual["objects"] = objects
        if vtype == "pivotTable":
            objects = {"subTotals": [{"properties": {"rowSubtotals": lit("false"), "columnSubtotals": lit("false")}}],
                       **(objects or {})}
            visual["objects"] = objects
        if vtype == "slicer":
            visual.setdefault("objects", {})["header"] = [{"properties": {"show": lit("false")}}]
        if vtype == "card" and h < 80:   # compact cards: smaller value and label so nothing clips
            visual.setdefault("objects", {}).update({
                "labels": [{"properties": {"fontSize": lit("14D")}}],
                "categoryLabels": [{"properties": {"fontSize": lit("8D")}}]})
        vco = {}
        if title:
            vco["title"] = [{"properties": {"show": lit("true"), "text": lit(f"'{title}'")}}]
            vco["subTitle"] = [{"properties": {"show": lit("false")}}]
        if extra_vco:
            vco.update(extra_vco)
        if vco:
            visual["visualContainerObjects"] = vco
        v = {"$schema": f"{SCH}/visualContainer/2.13.0/schema.json", "name": vname,
             "position": {"x": x, "y": y, "z": self.z * 1000, "width": w, "height": h, "tabOrder": self.z * 1000},
             "visual": visual}
        if filters:
            v["filterConfig"] = {"filters": filters}
        self.visuals.append(v)
        return vname

    def text(self, vname, x, y, w, h, runs):
        paragraphs = [{"textRuns": [{"value": t, "textStyle": st}]} for t, st in runs]
        self.add(vname, "textbox", x, y, w, h, objects={"general": [{"properties": {"paragraphs": paragraphs}}]})

    def slicer(self, vname, x, y, w, h, field, mode="Dropdown", title=None, single=False, default=None):
        objs = {"data": [{"properties": {"mode": lit(f"'{mode}'")}}]}
        if single:
            objs["selection"] = [{"properties": {"strictSingleSelect": lit("true")}}]
        if default:
            ent = field["Column"]["Expression"]["SourceRef"]["Entity"]
            prop = field["Column"]["Property"]
            objs["general"] = [{"properties": {"filter": {"filter": in_filter_expr(ent, prop, default)}}}]
        self.add(vname, "slicer", x, y, w, h, roles={"Values": [field]}, title=title, objects=objs)

    def no_filter(self, src, targets):
        self.interactions += [{"source": src, "target": t, "type": "NoFilter"} for t in targets]


H1 = {"fontWeight": "bold", "fontSize": "20pt", "color": "#285943"}
SMALL = {"fontSize": "9pt", "color": "#3C4A42"}
NOTE = "Gross value @ MSP = production x MSP: an estimate, not realised price and NOT farmer income."


def header(p, title, sub=NOTE):
    p.text("title", 16, 8, 900, 40, [(title, H1)])
    p.text("note", 16, 46, 1248, 26, [(sub, SMALL)])


def build_pages():
    yr = col("dim_year", "crop_year")
    pages = []
    msp_only = in_filter("dim_crop", "is_msp_crop", ["1L"], "fMsp")
    win = range_filter("dim_year", "crop_year", 2004, 2018, "fYears")

    # ---- Page 1
    p = Page("p1_overview", "1 Executive Overview", [win, msp_only])
    header(p, "Executive Agricultural Overview")
    cards = ["Gross Value @ MSP (Rs cr)", "Gross Value YoY %", "Gross Value CAGR %", "Area (M ha)", "Crops Covered", "Districts Covered"]
    for i, m in enumerate(cards):
        p.add(f"kpi{i}", "card", 16 + i * 167, 80, 160, 90, roles={"Values": [meas(m)]})
    p.slicer("sYear", 1020, 80, 244, 90, yr, mode="Between", title="Crop year")
    p.slicer("sGroup", 1020, 176, 120, 60, col("dim_crop", "crop_group"), title="Crop group")
    p.slicer("sRegion", 1144, 176, 120, 60, col("dim_state", "region"), title="Region")
    p.add("trend", "lineChart", 16, 180, 620, 300, roles={"Category": [yr], "Y": [meas("Gross Value @ MSP (Rs cr)"), meas("Gross Value Real 2018-19 (Rs cr)"), meas("Gross Value @ 2018 MSP (Rs cr)")]},
          title="Q9 Gross value: nominal vs real (CPI, 2018-19 Rs) vs volume (2018-19 MSP), Rs cr")
    p.add("mix", "treemap", 644, 180, 370, 300, roles={"Group": [col("dim_crop", "crop_group")], "Details": [col("dim_crop", "crop_name")],
                                                       "Values": [meas("Gross Value @ MSP (Rs cr)")]}, title="Q1 Value mix by crop group")
    p.add("statebars", "clusteredColumnChart", 16, 488, 1000, 224, roles={"Category": [col("dim_state", "state_name")], "Y": [meas("Gross Value @ MSP per ha (Rs)")]},
          title="Q3 Gross value per hectare by state (Rs/ha)", sort=(meas("Gross Value @ MSP per ha (Rs)"), "Descending"),
          filters=[measure_min_filter("MSP-valued Area (ha)", 500000, "fArea")])
    p.add("below26", "card", 1020, 244, 244, 120, roles={"Values": [meas("Quotes below MSP %")]},
          title="Mandi quotes below MSP, Jul-Sep 2026",
          filters=[in_filter("fact_market_price", "source_dataset", ["'AGMARKNET daily Jul-Sep 2026'"], "f26")])
    p.add("prov", "card", 1020, 372, 244, 70, roles={"Values": [meas("Provisional Year Flag")]})
    p.text("insight", 1020, 450, 244, 262, [("2004-05 to 2018-19: nominal x4.5, real (CPI) x1.73, volume x1.41. Most growth reflects MSP increases, which outpaced inflation by ~23%. "
                                            "Gross value = production x MSP: not farmer income.", {"fontSize": "10pt"})])
    pages.append(p)

    # ---- Page 2
    p = Page("p2_crops", "2 Crop Revenue & Profitability", [win, msp_only])
    header(p, "Crop Revenue & Profitability")
    p.slicer("sYear", 1020, 8, 244, 70, yr, mode="Between", title="Crop year")
    p.add("topcrops", "clusteredBarChart", 16, 80, 400, 330, roles={"Category": [col("dim_crop", "crop_name")], "Y": [meas("Gross Value @ MSP (Rs cr)")]},
          title="Q1 Estimated gross value by crop (Rs cr)", sort=(meas("Gross Value @ MSP (Rs cr)"), "Descending"))
    p.add("perha", "clusteredBarChart", 424, 80, 400, 330, roles={"Category": [col("dim_crop", "crop_name")], "Y": [meas("Gross Value @ MSP per ha (Rs)")]},
          title="Gross value per hectare (Rs/ha)", sort=(meas("Gross Value @ MSP per ha (Rs)"), "Descending"))
    p.add("scatter", "scatterChart", 832, 80, 432, 330,
          roles={"Category": [col("dim_crop", "crop_name")], "Series": [col("dim_crop", "crop_group")], "X": [meas("Area (M ha)")],
                 "Y": [meas("Gross Value @ MSP per ha (Rs)")], "Size": [meas("Gross Value @ MSP (Rs cr)")]},
          title="Q8 Footprint vs value per ha (bubble = total value)")
    p.add("profit", "tableEx", 16, 418, 760, 294,
          roles={"Values": [col("dim_crop", "crop_name"), meas("Gross Value @ MSP per ha (Rs)"), meas("A2+FL Cost per ha (Rs)"),
                            meas("C2 Cost per ha (Rs)"), meas("Est. Profit over A2+FL per ha (Rs)"), meas("Est. Profit over C2 per ha (Rs)"),
                            meas("Est. Profit over C2 per acre (Rs)"), meas("State-years with C2 Loss %")]},
          title="Q2 Estimated profit per ha where DES cost data exist (2008-09 to 2013-14, surveyed states)",
          filters=[range_filter("dim_year", "crop_year", 2008, 2013, "fCost")],
          sort=(meas("Est. Profit over C2 per ha (Rs)"), "Descending"))
    p.add("decomp", "barChart", 784, 418, 480, 294,
          roles={"Category": [col("agg_q04b_value_growth_decomposition", "crop_name")],
                 "Y": [agg("agg_q04b_value_growth_decomposition", "area_contribution_pct"),
                       agg("agg_q04b_value_growth_decomposition", "yield_contribution_pct"),
                       agg("agg_q04b_value_growth_decomposition", "price_msp_contribution_pct")]},
          title="Q4 Value growth 2004-06 to 2016-18: share from area / yield / MSP (%)")
    p.text("note2", 424, 8, 590, 70, [("Profit = APY yield x MSP - DES cost/ha. Valuing at MSP understates crops sold above MSP (pulses, cotton). Not farmer income.", SMALL)])
    pages.append(p)

    # ---- Page 3
    p = Page("p3_states", "3 State & District Analysis", [win, msp_only])
    header(p, "State / District Analysis")
    p.slicer("sYear", 1020, 8, 244, 70, yr, mode="Between", title="Crop year")
    p.slicer("sRegion", 860, 8, 150, 70, col("dim_state", "region"), title="Region")
    p.add("statebar", "clusteredBarChart", 16, 80, 360, 632, roles={"Category": [col("dim_state", "state_name")], "Y": [meas("Gross Value @ MSP per ha (Rs)")]},
          title="Q3 State ranking: gross value per ha (Rs)", sort=(meas("Gross Value @ MSP per ha (Rs)"), "Descending"),
          filters=[measure_min_filter("MSP-valued Area (ha)", 500000, "fArea")])
    p.add("matrix", "pivotTable", 384, 80, 500, 330, roles={"Rows": [col("dim_state", "state_name")], "Columns": [col("dim_crop", "crop_group")],
                                                          "Values": [meas("Gross Value @ MSP per ha (Rs)")]}, title="Gross value per ha: state x crop group")
    p.add("districts", "tableEx", 892, 80, 372, 330,
          roles={"Values": [col("dim_location", "district_name"), col("dim_location", "state_name"), meas("Gross Value @ MSP per ha (Rs)"),
                            meas("Gross Value @ MSP (Rs cr)")]},
          title="Top districts by value per ha (>= 2.5 lakh ha valued in window)",
          filters=[measure_min_filter("MSP-valued Area (ha)", 250000, "fDist")], sort=(meas("Gross Value @ MSP per ha (Rs)"), "Descending"))
    p.add("yield", "lineChart", 384, 418, 880, 294, roles={"Category": [yr], "Y": [meas("Yield (kg/ha)")], "Series": [col("dim_state", "state_name")]},
          title="Rice yield trend, top states (kg/ha) - change crop in the Filters pane",
          filters=[in_filter("dim_crop", "crop_name", ["'Rice'"], "fCrop"),
                   in_filter("dim_state", "state_name", ["'Punjab'", "'Uttar Pradesh'", "'West Bengal'", "'Odisha'", "'Andhra Pradesh'"], "fSt")])
    pages.append(p)

    # ---- Page 4
    p = Page("p4_mandi", "4 Mandi Price Intelligence")
    header(p, "Mandi Price Intelligence", "MSP comparison only for MSP-comparable forms (FAQ paddy, kapas, whole grain). MSP applies by marketing season (kharif Oct-Sep, rabi Apr-Mar).")
    p.slicer("sSrc", 16, 80, 300, 64, col("fact_market_price", "source_dataset"), title="Dataset", single=True, default=["'MH APMC monthly (CMO) 2014-16'"])
    p.slicer("sCrop", 324, 80, 200, 64, col("dim_crop", "crop_name"), title="Crop", single=True, default=["'Arhar/Tur'"])
    kp = ["Arrival-wtd Modal Price (Rs/qtl)", "Applicable MSP (Rs/qtl)", "Quotes below MSP %", "Modal Price CV %", "Markets Reporting"]
    for i, m in enumerate(kp):
        p.add(f"k{i}", "card", 532 + i * 148, 80, 142, 64, roles={"Values": [meas(m)]})
    p.add("mhline", "lineChart", 16, 152, 620, 270, roles={"Category": [col("dim_date", "year_month")],
                                                           "Y": [meas("Arrival-wtd Modal Price (Rs/qtl)"), meas("Applicable MSP (Rs/qtl)")]},
          title="Modal price vs applicable MSP by month (Rs/qtl)")
    p.add("mspcost", "lineChart", 644, 152, 620, 270, roles={"Category": [yr], "Y": [meas("MSP (Rs/qtl)"), meas("MSP Real 2018-19 (Rs/qtl)"), meas("CACP A2+FL Cost (Rs/qtl)")]},
          title="MSP nominal vs real (constant 2018-19 Rs, CPI) vs CACP A2+FL cost (Rs/qtl)",
          filters=[range_filter("dim_year", "crop_year", 2002, 2026, "fMspYr")])
    p.add("below", "clusteredBarChart", 16, 430, 400, 282, roles={"Category": [col("dim_crop", "crop_name")], "Y": [meas("Quotes below MSP %")]},
          title="Q6 Share of quotes below MSP", sort=(meas("Quotes below MSP %"), "Descending"))
    p.add("mspvm", "tableEx", 424, 430, 420, 282,
          roles={"Values": [col("dim_crop", "crop_name"), meas("Applicable MSP (Rs/qtl)"), meas("Median Modal Price (Rs/qtl)"),
                            meas("Median Mandi minus MSP (Rs/qtl)"), meas("Quotes below MSP %")]},
          title="MSP vs mandi price by crop (selected dataset)", sort=(meas("Quotes below MSP %"), "Descending"),
          objects={"values": [cf_color("Median Mandi minus MSP (Rs/qtl)", "Mandi vs MSP Color")]})
    p.add("vol", "tableEx", 852, 430, 412, 282,
          roles={"Values": [col("agg_q10a_market_volatility_mh", "market_name"), col("agg_q10a_market_volatility_mh", "crop_name"),
                            agg("agg_q10a_market_volatility_mh", "cv_pct", 1), agg("agg_q10a_market_volatility_mh", "max_min_ratio", 1)]},
          title="Q10 Most volatile APMC-crop pairs (MH)", sort=(agg("agg_q10a_market_volatility_mh", "cv_pct", 1), "Descending"))
    p.no_filter("sCrop", ["below", "mspvm"])
    pages.append(p)

    # ---- Page 5
    p = Page("p5_weather", "5 Weather & Yield", [range_filter("dim_year", "crop_year", 1997, 2015, "fRain")])
    header(p, "Weather / Yield Analysis", "Correlation of detrended yield with seasonal rainfall departure (1997-2015). Association only - not causal. State rain = mean of IMD subdivisions.")
    p.slicer("sCrop", 16, 80, 220, 64, col("dim_crop", "crop_name"), title="Crop", single=True, default=["'Groundnut'"])
    p.slicer("sState", 244, 80, 220, 64, col("dim_state", "state_name"), title="State")
    for i, m in enumerate(["Rain-Yield Correlation (r)", "Rain-Yield Pairs (n)", "Season Rain Departure %", "Yield Anomaly %"]):
        p.add(f"k{i}", "card", 472 + i * 198, 80, 190, 64, roles={"Values": [meas(m)]})
    p.add("scatter", "scatterChart", 16, 152, 620, 300,
          roles={"Category": [col("dim_state", "state_name"), yr], "X": [agg("fact_state_crop_year", "season_rain_dep_pct")],
                 "Y": [agg("fact_state_crop_year", "yield_anomaly_pct")]},
          title="Q7 Seasonal rain departure (%) vs yield anomaly (%) - each dot a state-year")
    p.add("corr", "clusteredBarChart", 644, 152, 620, 300, roles={"Category": [col("agg_q07a_rain_yield_association", "crop_name")],
                                                                  "Y": [agg("agg_q07a_rain_yield_association", "pearson_r", 1)]},
          title="Pearson r by crop (pooled state-years)", sort=(agg("agg_q07a_rain_yield_association", "pearson_r", 1), "Descending"))
    p.add("cat", "clusteredColumnChart", 16, 460, 620, 252, roles={"Category": [col("fact_state_crop_year", "jjas_category")], "Y": [meas("Yield Anomaly %")]},
          title="Average yield anomaly by IMD monsoon category")
    p.add("monsoon", "lineChart", 644, 460, 620, 252, roles={"Category": [yr], "Y": [meas("Monsoon Departure %")]},
          title="Monsoon (Jun-Sep) departure from 1951-2000 mean")
    pages.append(p)

    # ---- Page 6
    p = Page("p6_quality", "6 Data Quality")
    header(p, "Data Quality", "2019-20 provisional: district sums diverge from DES estimates. 342 APY rows and 150 price rows excluded; 460 price rows flagged.")
    for i, m in enumerate(["Production Rows", "Rows Excluded/Flagged", "Validation Checks Divergent", "MSP Values Official %", "Districts Covered"]):
        p.add(f"k{i}", "card", 16 + i * 250, 80, 242, 70, roles={"Values": [meas(m)]})
    p.add("val", "clusteredBarChart", 16, 158, 420, 270, roles={"Category": [col("dq_validation", "crop_name")], "Y": [agg("dq_validation", "diff_pct", 1)]},
          title="District sum vs DES 3rd AE 2019-20 (% difference)")
    p.add("issues", "tableEx", 444, 158, 820, 270, roles={"Values": [col("dq_issues", "domain"), col("dq_issues", "issue"), col("dq_issues", "action"),
                                                                   agg("dq_issues", "n_rows")]}, title="Issues and handling")
    p.add("src", "tableEx", 16, 436, 760, 276, roles={"Values": [col("ref_sources", "dataset"), col("ref_sources", "publisher"),
                                                               col("ref_sources", "coverage"), col("ref_sources", "reliability_note")]}, title="Sources")
    p.add("msp", "tableEx", 784, 436, 480, 276, roles={"Values": [col("fact_msp", "msp_key"), col("fact_msp", "crop_year_label"),
                                                                agg("fact_msp", "msp_effective"), col("fact_msp", "verification"), col("fact_msp", "source_id")]},
          title="MSP provenance")
    pages.append(p)

    # ---- Page 7: 2026 season (showcase)
    G, M = "agg_q11g_season_2026_outlook", "agg_q11h_msp_2026_27_vs_cost"
    p = Page("p7_season2026", "7 Season 2026",
             [in_filter("fact_market_price", "source_dataset", ["'AGMARKNET daily Jul-Sep 2026'"], "f26")])
    header(p, "2026 Season: Mandi Prices vs Current and New MSP",
           "AGMARKNET daily 21-Jul to 24-Sep-2026, ~2,700 markets. Current MSP = KMS 2025-26 / RMS 2026-27; new MSP = KMS 2026-27 (from Oct-2026) / RMS 2027-28 (from Apr-2027). Pre-harvest prices: a benchmark, not realised farm-gate prices.")
    p.slicer("sCrop", 16, 80, 200, 64, col("dim_crop", "crop_name"), title="Crop", single=True, default=["'Rice'"])
    kp = ["Applicable MSP (Rs/qtl)", "Next MSP 2026-27 (Rs/qtl)", "Median Modal Price (Rs/qtl)", "Quotes below MSP %",
          "Quotes below Next MSP %", "Markets Reporting"]
    for i, m in enumerate(kp):
        p.add(f"k{i}", "card", 224 + i * 174, 80, 168, 64, roles={"Values": [meas(m)]})
    p.add("daily", "lineChart", 16, 152, 620, 280,
          roles={"Category": [col("dim_date", "price_date")],
                 "Y": [meas("Median Modal Price (Rs/qtl)"), meas("Applicable MSP (Rs/qtl)"), meas("Next MSP 2026-27 (Rs/qtl)")]},
          title="Daily median mandi price vs current and new MSP (Rs/qtl)")
    p.add("bands", "clusteredColumnChart", 644, 152, 620, 280,
          roles={"Category": [col("fact_market_price", "msp_price_band")], "Y": [meas("MSP-comparable Quotes")]},
          title="Price distribution: quotes by distance from current MSP",
          sort=(col("fact_market_price", "msp_price_band"), "Ascending"))
    p.add("outlook", "clusteredBarChart", 16, 440, 620, 272,
          roles={"Category": [col(G, "crop_name")], "Y": [agg(G, "pct_below_current_msp", 1), agg(G, "pct_below_next_msp", 1)]},
          title="All crops: % of quotes below current vs new MSP", sort=(agg(G, "pct_below_next_msp", 1), "Descending"))
    p.add("msp26", "tableEx", 644, 440, 620, 272,
          roles={"Values": [col(M, "msp_key"), col(M, "season"), agg(M, "msp_prev"), agg(M, "msp_effective"), agg(M, "hike_pct", 1),
                            agg(M, "a2fl_cost"), agg(M, "msp_over_a2fl_pct", 1), col(M, "source_id")]},
          title="New MSPs (Rs/qtl): previous, new, hike %, CACP A2+FL cost, margin %", sort=(agg(M, "hike_pct", 1), "Descending"))
    pages.append(p)

    # ---- Page 8: Crop Explorer (one crop, everything about it)
    p = Page("p8_explorer", "8 Crop Explorer", [msp_only])
    header(p, "Crop Explorer", "Pick a crop, states and years: production, yield, YoY growth, gross value @ MSP, nominal vs real MSP, mandi price gap and rainfall association. " + NOTE)
    p.slicer("sCrop", 16, 80, 220, 60, col("dim_crop", "crop_name"), title="Crop", single=True, default=["'Rice'"])
    p.slicer("sState", 244, 80, 220, 60, col("dim_state", "state_name"), title="State")
    p.add("sYear", "slicer", 472, 80, 360, 60, roles={"Values": [yr]}, title="Crop year",
          objects={"data": [{"properties": {"mode": lit("'Between'")}}],
                   "general": [{"properties": {"filter": {"filter": range_filter("dim_year", "crop_year", 2004, 2018, "x")["filter"]}}}]})
    p.add("unit", "card", 840, 80, 424, 60, roles={"Values": [meas("Production Unit")]}, title="Production unit")
    kp = ["Production (M t or M bales)", "Production YoY %", "Yield (kg/ha)", "Yield YoY %", "Gross Value @ MSP (Rs cr)",
          "Real MSP Change %", "Quotes below MSP %", "Rain-Yield Correlation (r)"]
    for i, m in enumerate(kp):
        p.add(f"k{i}", "card", 16 + i * 156, 148, 150, 70, roles={"Values": [meas(m)]})
    p.add("trend", "lineClusteredColumnComboChart", 16, 226, 620, 240,
          roles={"Category": [yr], "Y": [meas("Production (M t or M bales)")], "Y2": [meas("Yield (kg/ha)")]},
          title="Production (columns) and yield (line) by crop year")
    p.add("states", "clusteredBarChart", 644, 226, 620, 240,
          roles={"Category": [col("dim_state", "state_name")], "Y": [meas("Production (M t or M bales)")]},
          title="Production by state (selected years)", sort=(meas("Production (M t or M bales)"), "Descending"))
    p.add("msp", "lineChart", 16, 474, 500, 238,
          roles={"Category": [yr], "Y": [meas("MSP (Rs/qtl)"), meas("MSP Real 2018-19 (Rs/qtl)"), meas("CACP A2+FL Cost (Rs/qtl)")]},
          title="MSP nominal vs real (2018-19 Rs) vs A2+FL cost, 2002-03 to 2026-27",
          filters=[range_filter("dim_year", "crop_year", 2002, 2026, "fMspYr")])
    p.add("yoy", "tableEx", 524, 474, 740, 238,
          roles={"Values": [col("dim_year", "crop_year_label"), meas("Production (M t or M bales)"), meas("Production YoY %"),
                            meas("Yield (kg/ha)"), meas("Yield YoY %"), meas("Gross Value @ MSP (Rs cr)"), meas("Gross Value YoY %")]},
          title="Year-on-year growth (green = up, orange = down)", sort=(col("dim_year", "crop_year_label"), "Descending"),
          objects={"values": [cf_color("Production YoY %", "Production YoY Color"), cf_color("Yield YoY %", "Yield YoY Color"),
                              cf_color("Gross Value YoY %", "Gross Value YoY Color")]})
    p.no_filter("sYear", ["msp", "k5"])
    pages.append(p)
    return pages


def build_report(rp):
    d = rp / "definition"
    (d / "pages").mkdir(parents=True)
    (rp / "definition.pbir").write_text(json.dumps({
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}}, indent=2))
    (d / "version.json").write_text(json.dumps({"$schema": f"{SCH}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2))
    theme_dst = rp / "StaticResources" / "RegisteredResources"
    theme_dst.mkdir(parents=True)
    shutil.copy(ROOT / "power_bi" / "theme_agri_intel.json", theme_dst / "theme_agri_intel.json")
    base_dst = rp / "StaticResources" / "SharedResources" / "BaseThemes"
    base_dst.mkdir(parents=True)
    shutil.copy(ROOT / "power_bi" / f"Base_Theme_{BASE_THEME}.json", base_dst / f"{BASE_THEME}.json")
    rv = {"visual": "2.13.0", "report": "3.4.0", "page": "2.3.1"}
    (d / "report.json").write_text(json.dumps({
        "$schema": f"{SCH}/report/3.3.0/schema.json",
        "themeCollection": {"baseTheme": {"name": BASE_THEME, "reportVersionAtImport": rv, "type": "SharedResources"},
                            "customTheme": {"name": "theme_agri_intel.json", "reportVersionAtImport": rv, "type": "RegisteredResources"}},
        "objects": {"section": [{"properties": {"verticalAlignment": lit("'Top'")}}]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": BASE_THEME, "path": f"BaseThemes/{BASE_THEME}.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "theme_agri_intel.json", "path": "theme_agri_intel.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}}, indent=2))
    pages = build_pages()
    (d / "pages" / "pages.json").write_text(json.dumps({"$schema": f"{SCH}/pagesMetadata/1.1.0/schema.json",
                                                        "pageOrder": [p.pid for p in pages], "activePageName": pages[0].pid}, indent=2))
    for p in pages:
        pd_ = d / "pages" / p.pid
        (pd_ / "visuals").mkdir(parents=True)
        page = {"$schema": f"{SCH}/page/2.1.0/schema.json", "name": p.pid, "displayName": p.display,
                "displayOption": "FitToPage", "height": 720, "width": 1280}
        if p.filters:
            page["filterConfig"] = {"filters": p.filters}
        if p.interactions:
            page["visualInteractions"] = p.interactions
        (pd_ / "page.json").write_text(json.dumps(page, indent=2))
        for v in p.visuals:
            (pd_ / "visuals" / v["name"]).mkdir()
            (pd_ / "visuals" / v["name"] / "visual.json").write_text(json.dumps(v, indent=2))


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    build_model(OUT / f"{NAME}.SemanticModel")
    build_report(OUT / f"{NAME}.Report")
    (OUT / f"{NAME}.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}], "settings": {"enableAutoRecovery": True}}, indent=2))
    (OUT / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    print("written", OUT)


if __name__ == "__main__":
    main()
