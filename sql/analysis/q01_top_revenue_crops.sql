-- Q1. Which crops generate the highest estimated gross value (MSP-valued)?
-- Window: crop years 2014-15 .. 2018-19 (latest five non-provisional years). Rs crore per year (nominal).
SELECT c.crop_name, c.crop_group,
       ROUND(SUM(f.gross_value_msp_inr) / 1e7 / 5, 0)                        AS avg_annual_gross_value_crore,
       ROUND(100.0 * SUM(f.gross_value_msp_inr) /
             (SELECT SUM(gross_value_msp_inr) FROM fact_district_crop_year WHERE crop_year BETWEEN 2014 AND 2018), 1)
                                                                              AS share_of_msp_valued_pct,
       ROUND(SUM(f.area_ha) / 1e6 / 5, 2)                                     AS avg_area_mha,
       ROUND(SUM(f.gross_value_msp_inr) / SUM(f.area_ha), 0)                  AS gross_value_per_ha
FROM fact_district_crop_year f JOIN dim_crop c USING (crop_id)
WHERE f.crop_year BETWEEN 2014 AND 2018 AND f.gross_value_msp_inr IS NOT NULL
GROUP BY c.crop_name, c.crop_group
ORDER BY avg_annual_gross_value_crore DESC;
