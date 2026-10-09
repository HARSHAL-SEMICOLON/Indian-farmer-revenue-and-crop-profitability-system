-- Q2. Estimated profit per hectare / acre - ONLY where DES cost exists (state x crop x year, 2008-09..2013-14).
-- Area-weighted across the states surveyed. Gross value = APY yield x MSP (not realised price).
SELECT f.crop_name,
       COUNT(*)                                                                 AS state_years,
       COUNT(DISTINCT f.state_id)                                               AS states,
       ROUND(SUM(f.gross_value_msp_per_ha * f.area_ha) / SUM(f.area_ha), 0)     AS gross_value_per_ha,
       ROUND(SUM(f.a2fl_per_ha * f.area_ha) / SUM(f.area_ha), 0)                AS cost_a2fl_per_ha,
       ROUND(SUM(f.c2_per_ha * f.area_ha) / SUM(f.area_ha), 0)                  AS cost_c2_per_ha,
       ROUND(SUM(f.est_profit_a2fl_per_ha * f.area_ha) / SUM(f.area_ha), 0)     AS est_profit_a2fl_per_ha,
       ROUND(SUM(f.est_profit_c2_per_ha * f.area_ha) / SUM(f.area_ha), 0)       AS est_profit_c2_per_ha,
       ROUND(SUM(f.est_profit_c2_per_acre * f.area_ha) / SUM(f.area_ha), 0)     AS est_profit_c2_per_acre,
       ROUND(100.0 * SUM(CASE WHEN f.est_profit_c2_per_ha < 0 THEN 1 ELSE 0 END) / COUNT(*), 0) AS pct_state_years_c2_loss,
       ROUND(AVG(f.apy_vs_coc_yield_ratio), 2)                                  AS avg_apy_to_coc_yield_ratio
FROM fact_state_crop_year f
WHERE f.est_profit_c2_per_ha IS NOT NULL
GROUP BY f.crop_name
ORDER BY est_profit_c2_per_ha DESC;
