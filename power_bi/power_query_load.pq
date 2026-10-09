// =====================================================================================
// Power Query (M) loader - paste into Advanced Editor of a Blank Query named fnLoad,
// then create one query per table:   = fnLoad("dim_crop")   etc.
// Set the parameter ExportFolder (Home > Manage Parameters > New, type Text) to e.g.
//   E:\DA PROJECTS\Indian Farmer Revenue Intelligence\power_bi\data\
// =====================================================================================
(tableName as text) as table =>
let
    Source   = Csv.Document(File.Contents(ExportFolder & tableName & ".csv"),
                            [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // numeric columns: everything that is not a known text column
    TextCols = {"crop_name","apy_name","crop_group","primary_season","apy_unit","price_form","msp_key",
                "state_name","region","state_group","imd_subdivisions","district_name","district_key",
                "crop_year_label","kharif_marketing_season","rabi_marketing_season","decade",
                "market_name","first_seen_in","month_name","year_month","agri_year_label","season_window",
                "season","dq_flag","valuation_basis","source_dataset","granularity","commodity_raw","variety",
                "jjas_category","rainfall_basis","rain_metric","marketing_season","source_id","source_title",
                "source_url","verification","note","source","subdivision","domain","issue","action","detail",
                "dimension","member","metric","check_name","unit","official_source","status","dataset",
                "publisher","coverage","grain","used_for","access_route","url","reliability_note","price_date",
                "quadrant","rain_band","cheapest_state","dearest_state","significant_5pct"},
    Cols     = Table.ColumnNames(Promoted),
    NumCols  = List.Difference(Cols, TextCols),
    Typed    = Table.TransformColumnTypes(Promoted,
                 List.Transform(NumCols, each {_, type number}) &
                 List.Transform(List.Intersect({Cols, TextCols}), each {_, type text}), "en-US"),
    WithDate = if List.Contains(Cols, "price_date")
               then Table.TransformColumnTypes(Typed, {{"price_date", type date}}, "en-US") else Typed
in
    WithDate
