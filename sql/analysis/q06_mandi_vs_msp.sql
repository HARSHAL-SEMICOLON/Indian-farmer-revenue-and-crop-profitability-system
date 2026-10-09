-- Q6. Modal mandi price vs applicable MSP (comparable commodity forms only, valid rows).
SELECT p.source_dataset, c.crop_name, p.price_form,
       COUNT(*)                                                    AS n_quotes,
       ROUND(AVG(p.msp_applicable), 0)                             AS avg_msp,
       ROUND(AVG(p.modal_price), 0)                                AS avg_modal,
       ROUND(100.0 * AVG(p.modal_below_msp), 1)                    AS pct_quotes_below_msp,
       ROUND(AVG(p.modal_vs_msp_pct), 1)                           AS avg_modal_vs_msp_pct
FROM fact_market_price p JOIN dim_crop c USING (crop_id)
WHERE p.msp_applicable IS NOT NULL
GROUP BY p.source_dataset, c.crop_name, p.price_form
HAVING COUNT(*) >= 5
ORDER BY p.source_dataset, pct_quotes_below_msp DESC;
