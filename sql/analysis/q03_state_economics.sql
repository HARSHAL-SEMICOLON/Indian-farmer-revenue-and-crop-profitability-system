-- Q3a. State crop economics, crop years 2014-15..2018-19 (MSP-valued crops only).
SELECT s.state_name, s.region,
       ROUND(SUM(f.gross_value_msp_inr) / 1e7 / 5, 0)          AS avg_annual_gross_value_crore,
       ROUND(SUM(f.area_ha) / 1e6 / 5, 2)                      AS avg_valued_area_mha,
       ROUND(SUM(f.gross_value_msp_inr) / SUM(f.area_ha), 0)   AS gross_value_per_ha,
       COUNT(DISTINCT f.crop_id)                               AS n_crops
FROM fact_district_crop_year f JOIN dim_state s USING (state_id)
WHERE f.crop_year BETWEEN 2014 AND 2018 AND f.gross_value_msp_inr IS NOT NULL
GROUP BY s.state_name, s.region
HAVING SUM(f.area_ha) / 5 > 100000
ORDER BY gross_value_per_ha DESC;
