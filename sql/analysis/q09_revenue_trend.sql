-- Q9. National MSP-valued gross value by crop year (nominal Rs crore), MSP crops, 2004-05..2019-20 (2019 provisional).
SELECT f.crop_year, y.crop_year_label, y.is_provisional,
       ROUND(SUM(f.gross_value_msp_inr) / 1e7, 0) AS gross_value_crore,
       ROUND(SUM(f.area_ha) / 1e6, 2)             AS valued_area_mha,
       COUNT(DISTINCT f.crop_id)                  AS n_crops_valued
FROM fact_district_crop_year f JOIN dim_year y USING (crop_year)
WHERE f.gross_value_msp_inr IS NOT NULL
GROUP BY f.crop_year ORDER BY f.crop_year;
