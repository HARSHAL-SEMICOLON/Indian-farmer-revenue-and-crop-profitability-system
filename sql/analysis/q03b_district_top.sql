-- Q3b. Districts with the highest MSP-valued gross value per hectare (2014-15..2018-19, >= 50,000 ha/yr valued area)
SELECT l.state_name, l.district_name,
       ROUND(SUM(f.gross_value_msp_inr) / SUM(f.area_ha), 0)  AS gross_value_per_ha,
       ROUND(SUM(f.gross_value_msp_inr) / 1e7 / COUNT(DISTINCT f.crop_year), 0) AS avg_annual_gross_value_crore,
       ROUND(SUM(f.area_ha) / COUNT(DISTINCT f.crop_year), 0)  AS avg_valued_area_ha
FROM fact_district_crop_year f JOIN dim_location l USING (location_id)
WHERE f.crop_year BETWEEN 2014 AND 2018 AND f.gross_value_msp_inr IS NOT NULL
GROUP BY l.state_name, l.district_name
HAVING SUM(f.area_ha) / COUNT(DISTINCT f.crop_year) >= 50000
ORDER BY gross_value_per_ha DESC;
