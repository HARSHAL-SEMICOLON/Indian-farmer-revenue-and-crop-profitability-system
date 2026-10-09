-- =====================================================================================================
-- Indian Farmer Revenue Intelligence - business questions in SQL (SQLite 3.35+)
-- Techniques: filtering, GROUP BY + HAVING, INNER and LEFT JOIN, CASE, CTEs, window functions
--             (RANK, DENSE_RANK, ROW_NUMBER, NTILE, LAG, FIRST_VALUE, rolling AVG OVER ROWS,
--             SUM/AVG OVER), conditional aggregation, correlation from sums.
-- Run all:  python -m src.sql_queries      (results -> outputs/results/sql_*.csv)
-- Each query starts with a line "-- name: <id>" so the runner can split the file.
-- "Gross value" = production x MSP (an estimate at the support price). It is NOT farmer income.
-- =====================================================================================================


-- name: q01_top_crops_by_gross_value
-- Q1. Which crops generate the highest estimated gross value? Avg per year 2014-15..2018-19,
--     with rank and share of the total (window functions over the aggregated CTE).
WITH crop_totals AS (
    SELECT c.crop_name, c.crop_group,
           SUM(f.gross_value_msp_inr) / 5.0 / 1e7      AS avg_gross_value_cr,
           SUM(f.gross_value_real_2018_inr) / 5.0 / 1e7 AS avg_gross_value_real_cr,
           SUM(f.area_ha) / 5.0 / 1e6                  AS avg_area_mha
    FROM fact_district_crop_year f
    JOIN dim_crop c USING (crop_id)
    WHERE f.crop_year BETWEEN 2014 AND 2018
      AND f.gross_value_msp_inr IS NOT NULL
    GROUP BY c.crop_name, c.crop_group
)
SELECT RANK() OVER (ORDER BY avg_gross_value_cr DESC)                         AS value_rank,
       crop_name, crop_group,
       ROUND(avg_gross_value_cr, 0)                                            AS avg_gross_value_cr,
       ROUND(avg_gross_value_real_cr, 0)                                       AS avg_gross_value_real_2018_cr,
       ROUND(100.0 * avg_gross_value_cr / SUM(avg_gross_value_cr) OVER (), 1)  AS share_pct,
       ROUND(100.0 * SUM(avg_gross_value_cr) OVER (ORDER BY avg_gross_value_cr DESC)
             / SUM(avg_gross_value_cr) OVER (), 1)                             AS cumulative_share_pct,
       ROUND(avg_area_mha, 2)                                                  AS avg_area_mha,
       ROUND(avg_gross_value_cr * 1e7 / (avg_area_mha * 1e6), 0)               AS gross_value_per_ha
FROM crop_totals
ORDER BY value_rank;


-- name: q02_profit_per_ha_where_cost_exists
-- Q2. Estimated profit per ha / acre over A2+FL and C2 - only state-crop-years with official DES cost.
WITH costed AS (
    SELECT crop_name, state_name, crop_year, area_ha,
           gross_value_msp_per_ha, a2fl_per_ha, c2_per_ha,
           est_profit_a2fl_per_ha, est_profit_c2_per_ha
    FROM fact_state_crop_year
    WHERE est_profit_c2_per_ha IS NOT NULL
),
by_crop AS (
    SELECT crop_name,
           COUNT(*)                                                         AS state_years,
           SUM(gross_value_msp_per_ha * area_ha) / SUM(area_ha)             AS gross_value_per_ha,
           SUM(c2_per_ha * area_ha) / SUM(area_ha)                          AS c2_cost_per_ha,
           SUM(est_profit_a2fl_per_ha * area_ha) / SUM(area_ha)             AS profit_a2fl_per_ha,
           SUM(est_profit_c2_per_ha * area_ha) / SUM(area_ha)               AS profit_c2_per_ha,
           100.0 * SUM(CASE WHEN est_profit_c2_per_ha < 0 THEN 1 ELSE 0 END) / COUNT(*) AS pct_state_years_c2_loss
    FROM costed
    GROUP BY crop_name
)
SELECT RANK() OVER (ORDER BY profit_c2_per_ha DESC) AS profit_rank,
       crop_name, state_years,
       ROUND(gross_value_per_ha)        AS gross_value_per_ha,
       ROUND(c2_cost_per_ha)            AS c2_cost_per_ha,
       ROUND(profit_a2fl_per_ha)        AS est_profit_a2fl_per_ha,
       ROUND(profit_c2_per_ha)          AS est_profit_c2_per_ha,
       ROUND(profit_c2_per_ha / 2.47105) AS est_profit_c2_per_acre,
       ROUND(pct_state_years_c2_loss)   AS pct_state_years_c2_loss
FROM by_crop
ORDER BY profit_rank;


-- name: q03_best_district_per_state
-- Q3. Strongest crop economics: each state's top-3 districts by gross value per ha (ROW_NUMBER per state),
--     alongside the state's own value/ha and national rank (DENSE_RANK).
WITH district AS (
    SELECT l.state_name, l.district_name,
           SUM(f.gross_value_msp_inr) / SUM(f.area_ha) AS value_per_ha,
           SUM(f.area_ha) / 5.0                        AS avg_area_ha
    FROM fact_district_crop_year f
    JOIN dim_location l USING (location_id)
    WHERE f.crop_year BETWEEN 2014 AND 2018 AND f.gross_value_msp_inr IS NOT NULL
    GROUP BY l.state_name, l.district_name
    HAVING SUM(f.area_ha) / 5.0 >= 50000
),
state AS (
    SELECT l.state_name, SUM(f.gross_value_msp_inr) / SUM(f.area_ha) AS state_value_per_ha
    FROM fact_district_crop_year f JOIN dim_location l USING (location_id)
    WHERE f.crop_year BETWEEN 2014 AND 2018 AND f.gross_value_msp_inr IS NOT NULL
    GROUP BY l.state_name
    HAVING SUM(f.area_ha) / 5.0 >= 100000
),
ranked AS (
    SELECT d.*, s.state_value_per_ha,
           ROW_NUMBER() OVER (PARTITION BY d.state_name ORDER BY d.value_per_ha DESC) AS rank_in_state,
           DENSE_RANK() OVER (ORDER BY s.state_value_per_ha DESC)                   AS state_rank
    FROM district d JOIN state s USING (state_name)
)
SELECT state_rank, state_name, ROUND(state_value_per_ha) AS state_value_per_ha,
       rank_in_state, district_name, ROUND(value_per_ha) AS district_value_per_ha,
       ROUND(100.0 * (value_per_ha / state_value_per_ha - 1), 1) AS pct_above_state_avg
FROM ranked
WHERE rank_in_state <= 3
ORDER BY state_rank, rank_in_state;


-- name: q04_yield_quartiles_vs_value
-- Q4. How does yield affect value? Split district-crop-years into yield quartiles (NTILE) within each crop.
--     MSP is uniform within a crop-year, so value/ha moves with yield.
WITH base AS (
    SELECT c.crop_name, f.yield_kg_per_ha, f.gross_value_msp_per_ha, f.area_ha
    FROM fact_district_crop_year f JOIN dim_crop c USING (crop_id)
    WHERE f.crop_year BETWEEN 2014 AND 2018 AND f.gross_value_msp_inr IS NOT NULL AND f.area_ha >= 1000
),
q AS (
    SELECT *, NTILE(4) OVER (PARTITION BY crop_name ORDER BY yield_kg_per_ha) AS yield_quartile
    FROM base
),
agg AS (
    SELECT crop_name, yield_quartile, COUNT(*) AS district_years,
           AVG(yield_kg_per_ha) AS avg_yield, AVG(gross_value_msp_per_ha) AS avg_value_per_ha
    FROM q GROUP BY crop_name, yield_quartile
)
SELECT crop_name, yield_quartile, district_years,
       ROUND(avg_yield)        AS avg_yield_kg_per_ha,
       ROUND(avg_value_per_ha) AS avg_value_per_ha,
       ROUND(avg_value_per_ha / FIRST_VALUE(avg_value_per_ha) OVER (PARTITION BY crop_name ORDER BY yield_quartile), 2)
                               AS value_vs_bottom_quartile
FROM agg
WHERE crop_name IN ('Rice', 'Wheat', 'Cotton', 'Sugarcane', 'Soyabean', 'Gram', 'Arhar/Tur', 'Maize')
ORDER BY crop_name, yield_quartile;


-- name: q05_cross_market_dispersion_2026
-- Q5. How do mandi prices differ across markets? Daily cross-market coefficient of variation
--     (AGMARKNET Jul-Sep 2026), then the median day per crop via ROW_NUMBER.
WITH daily AS (
    SELECT c.crop_name, p.price_form, p.date_key,
           COUNT(*)                                                          AS markets,
           AVG(p.modal_price)                                                AS mean_price,
           SQRT(MAX(AVG(p.modal_price * p.modal_price) - AVG(p.modal_price) * AVG(p.modal_price), 0)) AS sd_price
    FROM fact_market_price p JOIN dim_crop c USING (crop_id)
    WHERE p.source_dataset = 'AGMARKNET daily Jul-Sep 2026' AND p.dq_flag NOT LIKE 'excluded%'
    GROUP BY c.crop_name, p.price_form, p.date_key
    HAVING COUNT(*) >= 10
),
cv AS (
    SELECT crop_name, price_form, 100.0 * sd_price / mean_price AS cv_pct, markets,
           ROW_NUMBER() OVER (PARTITION BY crop_name, price_form ORDER BY 100.0 * sd_price / mean_price) AS rn,
           COUNT(*)     OVER (PARTITION BY crop_name, price_form)                                        AS n_days
    FROM daily
)
SELECT crop_name, price_form, n_days,
       ROUND(AVG(markets))  AS avg_markets_per_day,
       ROUND(AVG(cv_pct), 1) AS median_daily_cv_pct
FROM cv
WHERE rn IN ((n_days + 1) / 2, (n_days + 2) / 2)     -- median day(s)
GROUP BY crop_name, price_form, n_days
HAVING n_days >= 10
ORDER BY median_daily_cv_pct DESC;


-- name: q06_msp_gap_by_month_2026
-- Q6. Modal price vs MSP, MSP-comparable forms only, by month, with month-on-month change (LAG).
WITH monthly AS (
    SELECT c.crop_name, d.year_month,
           COUNT(*)                                     AS quotes,
           AVG(p.msp_applicable)                        AS msp,
           AVG(p.modal_price)                           AS avg_modal,
           100.0 * AVG(p.modal_below_msp)               AS pct_below_msp
    FROM fact_market_price p
    JOIN dim_crop c USING (crop_id)
    JOIN dim_date d USING (date_key)
    WHERE p.source_dataset = 'AGMARKNET daily Jul-Sep 2026' AND p.msp_applicable IS NOT NULL
    GROUP BY c.crop_name, d.year_month
    HAVING COUNT(*) >= 30
)
SELECT crop_name, year_month, quotes, ROUND(msp) AS msp, ROUND(avg_modal) AS avg_modal,
       ROUND(100.0 * (avg_modal / msp - 1), 1)                                          AS modal_vs_msp_pct,
       ROUND(pct_below_msp, 1)                                                          AS pct_quotes_below_msp,
       ROUND(pct_below_msp - LAG(pct_below_msp) OVER (PARTITION BY crop_name ORDER BY year_month), 1)
                                                                                        AS change_vs_prev_month_pp
FROM monthly
ORDER BY crop_name, year_month;


-- name: q07_rain_yield_correlation
-- Q7. Rainfall vs yield (association only): Pearson r per crop computed from sums in SQL.
WITH pts AS (
    SELECT crop_name, season_rain_dep_pct AS x, yield_anomaly_pct AS y
    FROM fact_state_crop_year
    WHERE yield_anomaly_pct IS NOT NULL AND season_rain_dep_pct IS NOT NULL
),
s AS (
    SELECT crop_name, COUNT(*) AS n,
           SUM(x) AS sx, SUM(y) AS sy, SUM(x * x) AS sxx, SUM(y * y) AS syy, SUM(x * y) AS sxy
    FROM pts GROUP BY crop_name HAVING COUNT(*) >= 30
)
SELECT crop_name, n AS state_years,
       ROUND((n * sxy - sx * sy) / SQRT((n * sxx - sx * sx) * (n * syy - sy * sy)), 3) AS pearson_r,
       ROUND(10 * (n * sxy - sx * sy) / (n * sxx - sx * sx), 2)                        AS yield_pp_per_10pct_rain,
       RANK() OVER (ORDER BY (n * sxy - sx * sy) / SQRT((n * sxx - sx * sx) * (n * syy - sy * sy)) DESC) AS r_rank
FROM s
ORDER BY r_rank;


-- name: q08_footprint_vs_profitability
-- Q8. High production but low profitability: compare each crop's area and value/ha with the
--     cross-crop average (AVG OVER ()), and attach C2 profit where cost data exist.
WITH crop AS (
    SELECT c.crop_name,
           SUM(f.area_ha) / 5.0 / 1e6                   AS avg_area_mha,
           SUM(f.gross_value_msp_inr) / SUM(f.area_ha)  AS value_per_ha
    FROM fact_district_crop_year f JOIN dim_crop c USING (crop_id)
    WHERE f.crop_year BETWEEN 2014 AND 2018 AND f.gross_value_msp_inr IS NOT NULL
    GROUP BY c.crop_name
),
profit AS (
    SELECT crop_name, SUM(est_profit_c2_per_ha * area_ha) / SUM(area_ha) AS profit_c2_per_ha
    FROM fact_state_crop_year WHERE est_profit_c2_per_ha IS NOT NULL GROUP BY crop_name
)
SELECT c.crop_name, ROUND(c.avg_area_mha, 2) AS avg_area_mha, ROUND(c.value_per_ha) AS value_per_ha,
       ROUND(p.profit_c2_per_ha) AS est_profit_c2_per_ha,
       CASE WHEN c.avg_area_mha >= AVG(c.avg_area_mha) OVER () AND c.value_per_ha < AVG(c.value_per_ha) OVER ()
                 THEN 'Large footprint, low value/ha'
            WHEN c.avg_area_mha >= AVG(c.avg_area_mha) OVER () AND p.profit_c2_per_ha < 0
                 THEN 'Large footprint, loss over C2 at MSP'
            WHEN c.avg_area_mha >= AVG(c.avg_area_mha) OVER () THEN 'Large footprint, healthy'
            ELSE 'Smaller footprint' END AS segment
FROM crop c LEFT JOIN profit p USING (crop_name)
ORDER BY c.avg_area_mha DESC;


-- name: q09_value_over_time
-- Q9. How has value changed over time? Nominal vs real (CPI, 2018-19 Rs) vs volume (2018-19 MSP),
--     with year-on-year growth (LAG) and index vs the first year (FIRST_VALUE).
WITH yearly AS (
    SELECT crop_year,
           SUM(gross_value_msp_inr) / 1e7         AS nominal_cr,
           SUM(gross_value_real_2018_inr) / 1e7   AS real_cr,
           SUM(gross_value_at_2018_msp_inr) / 1e7 AS volume_cr
    FROM fact_district_crop_year
    WHERE gross_value_msp_inr IS NOT NULL
    GROUP BY crop_year
)
SELECT y.crop_year, d.crop_year_label, d.is_provisional,
       ROUND(nominal_cr) AS nominal_cr, ROUND(real_cr) AS real_2018_cr, ROUND(volume_cr) AS volume_2018_msp_cr,
       ROUND(100.0 * (nominal_cr / LAG(nominal_cr) OVER w - 1), 1) AS nominal_yoy_pct,
       ROUND(100.0 * (real_cr / LAG(real_cr) OVER w - 1), 1)       AS real_yoy_pct,
       ROUND(100.0 * nominal_cr / FIRST_VALUE(nominal_cr) OVER w, 1) AS nominal_index,
       ROUND(100.0 * real_cr / FIRST_VALUE(real_cr) OVER w, 1)       AS real_index,
       ROUND(100.0 * volume_cr / FIRST_VALUE(volume_cr) OVER w, 1)   AS volume_index
FROM yearly y JOIN dim_year d USING (crop_year)
WINDOW w AS (ORDER BY y.crop_year)
ORDER BY y.crop_year;


-- name: q10_most_volatile_markets_2026
-- Q10. Which markets show large price variation? CV of daily modal price per market x crop
--      (>= 30 trading days, Jul-Sep 2026), top 5 per crop via ROW_NUMBER.
WITH mc AS (
    SELECT c.crop_name, p.price_form, m.state_name, m.market_name,
           COUNT(DISTINCT p.date_key) AS trading_days,
           AVG(p.modal_price)         AS mean_price,
           MIN(p.modal_price)         AS min_price,
           MAX(p.modal_price)         AS max_price,
           SQRT(MAX(AVG(p.modal_price * p.modal_price) - AVG(p.modal_price) * AVG(p.modal_price), 0)) AS sd_price
    FROM fact_market_price p
    JOIN dim_crop c USING (crop_id)
    JOIN dim_market m USING (market_id)
    WHERE p.source_dataset = 'AGMARKNET daily Jul-Sep 2026' AND p.dq_flag NOT LIKE 'excluded%'
    GROUP BY c.crop_name, p.price_form, m.state_name, m.market_name
    HAVING COUNT(DISTINCT p.date_key) >= 30
),
ranked AS (
    SELECT *, 100.0 * sd_price / mean_price AS cv_pct,
           ROW_NUMBER() OVER (PARTITION BY crop_name, price_form ORDER BY sd_price / mean_price DESC) AS rn
    FROM mc
)
SELECT crop_name, price_form, rn AS rank_in_crop, state_name, market_name, trading_days,
       ROUND(mean_price) AS mean_modal, ROUND(cv_pct, 1) AS cv_pct, ROUND(max_price / min_price, 2) AS max_min_ratio
FROM ranked
WHERE rn <= 5
ORDER BY cv_pct DESC;


-- name: q11_state_production_yoy
-- Q11. Which states had the highest year-on-year production growth in 2018-19 (rice, wheat)?
--      LAG partitioned by state and crop; HAVING keeps states with >= 1 lakh ha; RANK within crop.
WITH state_year AS (
    SELECT c.crop_name, s.state_name, f.crop_year,
           SUM(f.production_apy_unit) AS production_t,
           SUM(f.area_ha)             AS area_ha
    FROM fact_district_crop_year f
    JOIN dim_crop c     ON c.crop_id = f.crop_id
    JOIN dim_location l ON l.location_id = f.location_id
    JOIN dim_state s    ON s.state_id = l.state_id
    WHERE c.crop_name IN ('Rice', 'Wheat') AND f.crop_year BETWEEN 2016 AND 2018
    GROUP BY c.crop_name, s.state_name, f.crop_year
    HAVING SUM(f.area_ha) >= 100000
),
with_lag AS (
    SELECT *, LAG(production_t) OVER (PARTITION BY crop_name, state_name ORDER BY crop_year) AS prev_production_t
    FROM state_year
)
SELECT crop_name, state_name,
       ROUND(prev_production_t / 1e6, 2)                       AS production_2017_mt,
       ROUND(production_t / 1e6, 2)                            AS production_2018_mt,
       ROUND(100.0 * (production_t / prev_production_t - 1), 1) AS yoy_growth_pct,
       RANK() OVER (PARTITION BY crop_name ORDER BY production_t / prev_production_t DESC) AS growth_rank,
       CASE WHEN production_t >= prev_production_t * 1.10 THEN 'strong growth (>=10%)'
            WHEN production_t >= prev_production_t        THEN 'growth'
            ELSE 'decline' END                                 AS trend
FROM with_lag
WHERE crop_year = 2018 AND prev_production_t > 0
ORDER BY crop_name, growth_rank;


-- name: q12_real_msp_vs_inflation
-- Q12. Did MSPs rise faster than consumer prices? 2004-05 vs 2024-25 MSP in nominal and real
--      (constant 2018-19 Rs, CPI) terms. Conditional aggregation pivots the two years; CASE labels.
WITH two_years AS (
    SELECT m.msp_key, m.season,
           MAX(CASE WHEN m.crop_year = 2004 THEN m.msp_effective END) AS msp_2004,
           MAX(CASE WHEN m.crop_year = 2024 THEN m.msp_effective END) AS msp_2024,
           MAX(CASE WHEN m.crop_year = 2004 THEN m.msp_real_2018 END) AS real_2004,
           MAX(CASE WHEN m.crop_year = 2024 THEN m.msp_real_2018 END) AS real_2024
    FROM fact_msp m
    JOIN dim_year y ON y.crop_year = m.crop_year
    WHERE y.cpi_deflator_2018_100 IS NOT NULL
    GROUP BY m.msp_key, m.season
    HAVING COUNT(DISTINCT m.crop_year) > 1
)
SELECT msp_key, season, msp_2004, msp_2024,
       ROUND(100.0 * (msp_2024 / msp_2004 - 1), 1)   AS nominal_growth_pct,
       ROUND(100.0 * (real_2024 / real_2004 - 1), 1) AS real_growth_pct,
       CASE WHEN real_2024 > real_2004 * 1.5 THEN 'far ahead of inflation (>50% real)'
            WHEN real_2024 > real_2004        THEN 'ahead of inflation'
            ELSE 'lagged inflation' END             AS verdict
FROM two_years
WHERE msp_2004 IS NOT NULL AND msp_2024 IS NOT NULL
ORDER BY real_growth_pct DESC;


-- name: q13_rolling_yield
-- Q13. National yield with a 3-year rolling average (smooths weather shocks), major crops.
WITH national AS (
    SELECT c.crop_name, f.crop_year,
           SUM(f.production_apy_unit) / SUM(f.area_ha) AS yield_unit_per_ha
    FROM fact_district_crop_year f
    JOIN dim_crop c USING (crop_id)
    WHERE c.crop_name IN ('Rice', 'Wheat', 'Maize', 'Gram', 'Soyabean')
      AND f.crop_year BETWEEN 1997 AND 2018 AND f.area_ha > 0
    GROUP BY c.crop_name, f.crop_year
)
SELECT crop_name, crop_year,
       ROUND(yield_unit_per_ha, 3) AS yield_t_per_ha,
       ROUND(AVG(yield_unit_per_ha) OVER (PARTITION BY crop_name ORDER BY crop_year
                                          ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 3) AS yield_3yr_avg,
       ROUND(100.0 * (yield_unit_per_ha / AVG(yield_unit_per_ha) OVER (PARTITION BY crop_name ORDER BY crop_year
                                          ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) - 1), 1) AS vs_prev_3yr_avg_pct
FROM national
ORDER BY crop_name, crop_year;


-- name: q14_data_coverage_audit
-- Q14. Which crops can be valued, priced and costed? LEFT JOINs keep crops with no MSP, no prices or no
--      cost data (they would vanish with INNER JOIN), so the gaps are visible.
WITH msp AS (SELECT crop_id, COUNT(*) AS msp_years, MIN(crop_year) AS first_msp, MAX(crop_year) AS last_msp
             FROM fact_msp GROUP BY crop_id),
     price AS (SELECT crop_id, COUNT(*) AS quotes, SUM(msp_comparable) AS msp_comparable_quotes
               FROM fact_market_price WHERE dq_flag NOT LIKE 'excluded%' GROUP BY crop_id),
     cost AS (SELECT crop_id, COUNT(*) AS cost_state_years FROM fact_cost_of_cultivation GROUP BY crop_id)
SELECT c.crop_name, c.crop_group,
       COALESCE(m.msp_years, 0)       AS msp_years, m.first_msp, m.last_msp,
       COALESCE(p.quotes, 0)          AS mandi_quotes,
       COALESCE(p.msp_comparable_quotes, 0) AS msp_comparable_quotes,
       COALESCE(k.cost_state_years, 0) AS cost_state_years,
       CASE WHEN m.crop_id IS NULL THEN 'no MSP: price analysis only'
            WHEN k.crop_id IS NULL THEN 'valued at MSP, no profit estimate'
            ELSE 'valued and profit-estimated' END AS analysis_scope
FROM dim_crop c
LEFT JOIN msp m   ON m.crop_id = c.crop_id
LEFT JOIN price p ON p.crop_id = c.crop_id
LEFT JOIN cost k  ON k.crop_id = c.crop_id
ORDER BY analysis_scope, c.crop_name;


-- name: q15_season_2026_outlook
-- Q15. 2026 season: share of Jul-Sep 2026 quotes below the current MSP and below the newly announced MSP.
WITH next_msp AS (
    SELECT crop_id, msp_effective AS msp_next FROM fact_msp WHERE crop_year = 2026
),
quotes AS (
    SELECT c.crop_name, p.price_form, p.modal_price, p.msp_applicable, n.msp_next
    FROM fact_market_price p
    JOIN dim_crop c  ON c.crop_id = p.crop_id
    JOIN next_msp n ON n.crop_id = p.crop_id
    WHERE p.source_dataset = 'AGMARKNET daily Jul-Sep 2026'
      AND p.msp_applicable IS NOT NULL AND p.dq_flag NOT LIKE 'excluded%'
)
SELECT crop_name, price_form, COUNT(*) AS quotes,
       MAX(msp_applicable) AS msp_current, MAX(msp_next) AS msp_next,
       ROUND(100.0 * (MAX(msp_next) / MAX(msp_applicable) - 1), 1)              AS msp_hike_pct,
       ROUND(100.0 * AVG(CASE WHEN modal_price < msp_applicable THEN 1.0 ELSE 0 END), 1) AS pct_below_current_msp,
       ROUND(100.0 * AVG(CASE WHEN modal_price < msp_next THEN 1.0 ELSE 0 END), 1)       AS pct_below_next_msp
FROM quotes
GROUP BY crop_name, price_form
HAVING COUNT(*) >= 30
ORDER BY pct_below_next_msp DESC;
