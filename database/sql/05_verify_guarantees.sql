-- Business Management Platform, Phase 2: verification of guarantees G-01 to G-38 (docs/03_database_design.md
-- section 8.2) and the data dependencies required by the evaluation suite (docs/06_evaluation_plan.md section 12).
--
-- Read-only: the whole script runs inside one transaction that is ROLLED BACK at the end, so the helper schema
-- and functions it creates to compute the statistical tests (Welch t-test, one-way ANOVA, chi-square, a
-- two-proportion z-test and Spearman correlation -- none of which PostgreSQL has built in) never persist, and no
-- row of business data is read for any purpose other than producing the printed checks below.
--
-- Usage:  psql -d bmp -f 05_verify_guarantees.sql            (any role with SELECT may run it)
-- Each guarantee prints as one or more rows of (measured value columns ..., pass). Scan the output for `f`
-- (false) in the right-most "pass" column; everything else is context for that row's measurement.

\pset format aligned
\pset border 1
\timing off

\set ON_ERROR_ROLLBACK on
BEGIN;
SET LOCAL statement_timeout = 0;

CREATE SCHEMA verify;
SET LOCAL search_path = verify, public;

-- =========================================================================================================
-- Statistics helpers: erf / normal CDF (Abramowitz-Stegun 7.1.26), log-gamma (Lanczos), the regularized
-- incomplete beta function (Numerical Recipes betacf/betai) for the t- and F- distributions, and the
-- regularized incomplete gamma function (Numerical Recipes gser/gcf) for the chi-square distribution.
-- =========================================================================================================

CREATE FUNCTION verify.erf(x double precision) RETURNS double precision AS $$
DECLARE t double precision; y double precision; s double precision;
BEGIN
  s := sign(x); x := abs(x);
  t := 1.0 / (1.0 + 0.3275911 * x);
  y := 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * verify.exp_safe(-x * x);
  RETURN s * y;
END; $$ LANGUAGE plpgsql IMMUTABLE;

CREATE FUNCTION verify.norm_cdf(z double precision) RETURNS double precision AS $$
  SELECT 0.5 * (1.0 + verify.erf(z / sqrt(2.0)));
$$ LANGUAGE sql IMMUTABLE;

-- exp() that returns 0/+Infinity instead of erroring on underflow/overflow (PostgreSQL's own exp() raises
-- "value out of range: underflow" when the true result would round to exactly 0.0, which routinely happens
-- for the very small tail probabilities these tests produce on a 100k+ row dataset)
CREATE FUNCTION verify.exp_safe(x double precision) RETURNS double precision AS $$
  SELECT CASE WHEN x < -700 THEN 0.0 WHEN x > 700 THEN 'Infinity'::double precision ELSE exp(x) END;
$$ LANGUAGE sql IMMUTABLE;

CREATE FUNCTION verify.lgamma(x double precision) RETURNS double precision AS $$
DECLARE
  g CONSTANT double precision := 7.0;
  c CONSTANT double precision[] := ARRAY[0.99999999999980993, 676.5203681218851, -1259.1392167224028,
    771.32342877765313, -176.61502916214059, 12.507343278686905, -0.13857109526572012,
    9.9843695780195716e-6, 1.5056327351493116e-7];
  xx double precision; a double precision; t double precision; i int;
BEGIN
  xx := x - 1.0;
  a := c[1];
  FOR i IN 1..8 LOOP
    a := a + c[i + 1] / (xx + i);
  END LOOP;
  t := xx + g + 0.5;
  RETURN 0.5 * ln(2 * pi()) + (xx + 0.5) * ln(t) - t + ln(a);
END; $$ LANGUAGE plpgsql IMMUTABLE;

CREATE FUNCTION verify.betacf(x double precision, a double precision, b double precision) RETURNS double precision AS $$
DECLARE
  FPMIN CONSTANT double precision := 1e-300; EPS CONSTANT double precision := 3e-12;
  qab double precision := a + b; qap double precision := a + 1; qam double precision := a - 1;
  c double precision := 1; d double precision; h double precision; m int; m2 double precision; aa double precision; del double precision;
BEGIN
  d := 1 - qab * x / qap;
  IF abs(d) < FPMIN THEN d := FPMIN; END IF;
  d := 1 / d; h := d;
  FOR m IN 1..300 LOOP
    m2 := 2.0 * m;
    aa := m * (b - m) * x / ((qam + m2) * (a + m2));
    d := 1 + aa * d; IF abs(d) < FPMIN THEN d := FPMIN; END IF;
    c := 1 + aa / c; IF abs(c) < FPMIN THEN c := FPMIN; END IF;
    d := 1 / d; h := h * d * c;
    aa := -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
    d := 1 + aa * d; IF abs(d) < FPMIN THEN d := FPMIN; END IF;
    c := 1 + aa / c; IF abs(c) < FPMIN THEN c := FPMIN; END IF;
    d := 1 / d; del := d * c; h := h * del;
    IF abs(del - 1.0) < EPS THEN EXIT; END IF;
  END LOOP;
  RETURN h;
END; $$ LANGUAGE plpgsql IMMUTABLE;

-- regularized incomplete beta I_x(a,b)
CREATE FUNCTION verify.ibeta(x double precision, a double precision, b double precision) RETURNS double precision AS $$
DECLARE bt double precision;
BEGIN
  IF x <= 0 THEN RETURN 0; END IF;
  IF x >= 1 THEN RETURN 1; END IF;
  bt := verify.exp_safe(verify.lgamma(a + b) - verify.lgamma(a) - verify.lgamma(b) + a * ln(x) + b * ln(1 - x));
  IF x < (a + 1) / (a + b + 2) THEN
    RETURN bt * verify.betacf(x, a, b) / a;
  ELSE
    RETURN 1 - bt * verify.betacf(1 - x, b, a) / b;
  END IF;
END; $$ LANGUAGE plpgsql IMMUTABLE;

-- two-sided p-value of Student's t with df degrees of freedom
CREATE FUNCTION verify.t_p2(t double precision, df double precision) RETURNS double precision AS $$
  SELECT verify.ibeta(df / (df + t * t), df / 2.0, 0.5);
$$ LANGUAGE sql IMMUTABLE;

-- upper-tail p-value of an F statistic (one-way ANOVA)
CREATE FUNCTION verify.f_p(f double precision, d1 double precision, d2 double precision) RETURNS double precision AS $$
  SELECT 1 - verify.ibeta(d1 * f / (d1 * f + d2), d1 / 2.0, d2 / 2.0);
$$ LANGUAGE sql IMMUTABLE;

CREATE FUNCTION verify.gser(a double precision, x double precision) RETURNS double precision AS $$
DECLARE gln double precision := verify.lgamma(a); ap double precision := a; summ double precision; del double precision; n int;
BEGIN
  IF x <= 0 THEN RETURN 0; END IF;
  summ := 1.0 / a; del := summ;
  FOR n IN 1..500 LOOP
    ap := ap + 1; del := del * x / ap; summ := summ + del;
    IF abs(del) < abs(summ) * 1e-12 THEN EXIT; END IF;
  END LOOP;
  RETURN summ * verify.exp_safe(-x + a * ln(x) - gln);
END; $$ LANGUAGE plpgsql IMMUTABLE;

CREATE FUNCTION verify.gcf(a double precision, x double precision) RETURNS double precision AS $$
DECLARE
  FPMIN CONSTANT double precision := 1e-300; gln double precision := verify.lgamma(a);
  b double precision := x + 1 - a; c double precision := 1 / FPMIN; d double precision := 1 / b; h double precision := d;
  i int; an double precision; del double precision;
BEGIN
  FOR i IN 1..500 LOOP
    an := -i * (i - a);
    b := b + 2;
    d := an * d + b; IF abs(d) < FPMIN THEN d := FPMIN; END IF;
    c := b + an / c; IF abs(c) < FPMIN THEN c := FPMIN; END IF;
    d := 1 / d; del := d * c; h := h * del;
    IF abs(del - 1.0) < 1e-12 THEN EXIT; END IF;
  END LOOP;
  RETURN verify.exp_safe(-x + a * ln(x) - gln) * h;
END; $$ LANGUAGE plpgsql IMMUTABLE;

-- regularized lower incomplete gamma P(a,x) -- chi-square CDF is P(k/2, x/2)
CREATE FUNCTION verify.gammp(a double precision, x double precision) RETURNS double precision AS $$
  SELECT CASE WHEN x < a + 1 THEN verify.gser(a, x) ELSE 1 - verify.gcf(a, x) END;
$$ LANGUAGE sql IMMUTABLE;

CREATE FUNCTION verify.chi2_p(x double precision, k double precision) RETURNS double precision AS $$
  SELECT 1 - verify.gammp(k / 2.0, x / 2.0);
$$ LANGUAGE sql IMMUTABLE;

-- Welch's t-test: returns (t, df, p) for two samples given as arrays
CREATE FUNCTION verify.welch(s1 double precision[], s2 double precision[], OUT t double precision, OUT df double precision, OUT p double precision) AS $$
DECLARE n1 double precision := array_length(s1, 1); n2 double precision := array_length(s2, 1);
        m1 double precision; m2 double precision; v1 double precision; v2 double precision;
BEGIN
  SELECT avg(x), variance(x) INTO m1, v1 FROM unnest(s1) x;
  SELECT avg(x), variance(x) INTO m2, v2 FROM unnest(s2) x;
  t := (m1 - m2) / sqrt(v1 / n1 + v2 / n2);
  df := (v1 / n1 + v2 / n2) ^ 2 / ((v1 / n1) ^ 2 / (n1 - 1) + (v2 / n2) ^ 2 / (n2 - 1));
  p := verify.t_p2(t, df);
END; $$ LANGUAGE plpgsql;

\echo '=================================================================================================='
\echo 'STRUCTURE AND INTEGRITY'
\echo '=================================================================================================='

\echo '-- G-01 Coverage: calendar span, RYD-DC daily, each store >=98% of days'
SELECT count(*) AS calendar_rows, min(date_key) AS d0, max(date_key) AS d1,
       (count(*) = 1035 AND min(date_key) = '2024-01-01' AND max(date_key) = '2026-10-31') AS pass
FROM calendar;

WITH days AS (SELECT generate_series('2024-01-01'::date, '2026-10-31'::date, '1 day') d),
     dc AS (SELECT count(DISTINCT order_date) n FROM sales_orders WHERE branch_id = 9),
     store_cov AS (
       SELECT b.branch_id, count(DISTINCT o.order_date)::numeric / (SELECT count(*) FROM days) AS cov
       FROM branches b LEFT JOIN sales_orders o ON o.branch_id = b.branch_id AND o.channel = 'In-Store'
       WHERE b.branch_id BETWEEN 1 AND 8 GROUP BY b.branch_id)
SELECT (SELECT n FROM dc) = (SELECT count(*) FROM days) AS dc_every_day,
       min(cov) AS worst_store_coverage, (min(cov) >= 0.98) AS pass FROM store_cov;

\echo '-- G-02 Integrity: unique business keys; recomputed line_total/line_cost; no negative qty/price'
SELECT 'order_number' k, count(*) - count(DISTINCT order_number) dup FROM sales_orders
UNION ALL SELECT 'sku', count(*) - count(DISTINCT sku) FROM products
UNION ALL SELECT 'customer_code', count(*) - count(DISTINCT customer_code) FROM customers
UNION ALL SELECT 'po_number', count(*) - count(DISTINCT po_number) FROM purchase_orders
UNION ALL SELECT 'branch_code', count(*) - count(DISTINCT branch_code) FROM branches
UNION ALL SELECT 'supplier_code', count(*) - count(DISTINCT supplier_code) FROM suppliers;

SELECT count(*) AS mismatched_lines,
       count(*) FILTER (WHERE quantity < 0 OR unit_price < 0 OR unit_cost < 0) AS negative_rows,
       (count(*) = 0) AS pass
FROM sales_order_items
WHERE line_total <> round(quantity * unit_price * (1 - discount_pct / 100.0), 2)
   OR line_cost <> round(quantity * unit_cost, 2)
   OR quantity < 0 OR unit_price < 0 OR unit_cost < 0;

\echo '-- G-03 Order totals: subtotal/vat/total/items_count/discount_amount recomputation'
WITH agg AS (SELECT order_id, sum(line_total) subt, sum(quantity) itemsq, count(*) n,
                    sum(quantity * unit_price - line_total) disc FROM sales_order_items GROUP BY order_id)
SELECT count(*) AS mismatched_orders, (count(*) = 0) AS pass
FROM sales_orders o JOIN agg a ON a.order_id = o.order_id
WHERE o.subtotal_amount <> round(a.subt, 2)
   OR o.vat_amount <> round(0.15 * o.subtotal_amount, 2)
   OR o.total_amount <> round(o.subtotal_amount + o.vat_amount + o.shipping_fee, 2)
   OR o.items_count <> a.n
   OR o.discount_amount <> round(a.disc, 2);

\echo '-- G-04 Shipping fee rule'
SELECT count(*) AS violations, (count(*) = 0) AS pass FROM sales_orders o
LEFT JOIN customers c ON c.customer_id = o.customer_id
WHERE (o.channel IN ('Online', 'Mobile App') AND o.subtotal_amount < 250 AND coalesce(c.loyalty_tier, 'None') IN ('None', 'Silver') AND o.shipping_fee <> 25)
   OR NOT (o.channel IN ('Online', 'Mobile App') AND o.subtotal_amount < 250 AND coalesce(c.loyalty_tier, 'None') IN ('None', 'Silver')) AND o.shipping_fee <> 0;

\echo '-- G-05 Channel/location (Corporate interpreted as Business); delivery_city rule'
SELECT
  (SELECT count(*) FROM sales_orders WHERE channel = 'In-Store' AND branch_id = 9) AS instore_at_dc,
  (SELECT count(*) FROM sales_orders WHERE channel IN ('Online', 'Mobile App', 'B2B') AND branch_id <> 9) AS digital_not_at_dc,
  (SELECT count(*) FROM sales_orders WHERE channel = 'In-Store' AND delivery_city IS NOT NULL) AS instore_with_city,
  (SELECT count(*) FROM sales_orders WHERE channel <> 'In-Store' AND delivery_city IS NULL) AS digital_without_city,
  (SELECT count(*) FROM sales_orders o JOIN customers c ON c.customer_id = o.customer_id WHERE o.channel = 'B2B' AND c.customer_type <> 'Business') AS b2b_not_business,
  ((SELECT count(*) FROM sales_orders WHERE channel = 'In-Store' AND branch_id = 9) = 0
   AND (SELECT count(*) FROM sales_orders WHERE channel IN ('Online', 'Mobile App', 'B2B') AND branch_id <> 9) = 0
   AND (SELECT count(*) FROM sales_orders WHERE channel = 'In-Store' AND delivery_city IS NOT NULL) = 0
   AND (SELECT count(*) FROM sales_orders WHERE channel <> 'In-Store' AND delivery_city IS NULL) = 0
   AND (SELECT count(*) FROM sales_orders o JOIN customers c ON c.customer_id = o.customer_id WHERE o.channel = 'B2B' AND c.customer_type <> 'Business') = 0) AS pass;

\echo '-- G-06 Anonymous orders: 8%+-1 of In-Store orders have no customer; others all have one'
SELECT round(100.0 * count(*) FILTER (WHERE customer_id IS NULL) / count(*), 2) AS anon_pct_instore,
       (SELECT count(*) FROM sales_orders WHERE channel <> 'In-Store' AND customer_id IS NULL) AS digital_without_cust,
       (round(100.0 * count(*) FILTER (WHERE customer_id IS NULL) / count(*), 2) BETWEEN 7 AND 9
        AND (SELECT count(*) FROM sales_orders WHERE channel <> 'In-Store' AND customer_id IS NULL) = 0) AS pass
FROM sales_orders WHERE channel = 'In-Store';

\echo '-- G-07 Status mix (NOTE: doc says Completed 94-96%% overall, contradicted by its own sub-clauses -- see report)'
SELECT round(100.0 * count(*) FILTER (WHERE status = 'Completed') / count(*), 2) AS completed_pct_overall FROM sales_orders;
SELECT y, round(100.0 * count(*) FILTER (WHERE status = 'Cancelled') / count(*), 2) AS cancel_pct,
       (round(100.0 * count(*) FILTER (WHERE status = 'Cancelled') / count(*), 2) BETWEEN 2.0 AND 3.0) AS pass
FROM (SELECT extract(year FROM order_date)::int y, status FROM sales_orders WHERE channel IN ('Online', 'Mobile App')) s GROUP BY y ORDER BY y;
SELECT y, round(100.0 * count(*) FILTER (WHERE status = 'Cancelled') / count(*), 3) AS cancel_pct_instore,
       (round(100.0 * count(*) FILTER (WHERE status = 'Cancelled') / count(*), 3) < 0.5) AS pass
FROM (SELECT extract(year FROM order_date)::int y, status FROM sales_orders WHERE channel = 'In-Store') s GROUP BY y ORDER BY y;
SELECT y, round(100.0 * count(*) FILTER (WHERE status = 'Returned') / count(*), 2) AS returned_pct,
       (round(100.0 * count(*) FILTER (WHERE status = 'Returned') / count(*), 2) BETWEEN 0.5 AND 1.0) AS pass
FROM (SELECT extract(year FROM order_date)::int y, status FROM sales_orders) s GROUP BY y ORDER BY y;
SELECT count(*) AS processing_outside_window, (count(*) = 0) AS pass
FROM sales_orders WHERE status = 'Processing' AND order_date NOT BETWEEN '2026-10-29' AND '2026-10-31';

\echo '-- G-08 Payment methods'
SELECT
  (SELECT count(*) FROM sales_orders WHERE payment_method = 'Cash on Delivery' AND channel <> 'Online') AS cod_outside_online,
  (SELECT count(*) FROM sales_orders WHERE payment_method = 'Cash' AND channel <> 'In-Store') AS cash_outside_instore,
  (SELECT count(*) FROM sales_orders WHERE payment_method = 'Buy Now Pay Later' AND channel NOT IN ('Online', 'Mobile App')) AS bnpl_outside,
  (SELECT count(*) FROM sales_orders WHERE payment_method = 'Bank Transfer' AND channel <> 'B2B') AS bank_outside_b2b,
  (SELECT round(100.0 * count(*) FILTER (WHERE payment_method = 'Mada') / count(*), 1) FROM sales_orders WHERE channel = 'In-Store') AS mada_pct_instore,
  ((SELECT count(*) FROM sales_orders WHERE payment_method = 'Cash on Delivery' AND channel <> 'Online') = 0
   AND (SELECT count(*) FROM sales_orders WHERE payment_method = 'Cash' AND channel <> 'In-Store') = 0
   AND (SELECT count(*) FROM sales_orders WHERE payment_method = 'Buy Now Pay Later' AND channel NOT IN ('Online', 'Mobile App')) = 0
   AND (SELECT count(*) FROM sales_orders WHERE payment_method = 'Bank Transfer' AND channel <> 'B2B') = 0
   AND (SELECT round(100.0 * count(*) FILTER (WHERE payment_method = 'Mada') / count(*), 1) FROM sales_orders WHERE channel = 'In-Store') >= 40) AS pass;

\echo '=================================================================================================='
\echo 'SCALE, GROWTH AND RANKING'
\echo '=================================================================================================='

\echo '-- G-09 Volume'
SELECT (SELECT count(*) FROM sales_orders) AS orders, (SELECT count(*) FROM sales_order_items) AS lines,
       (SELECT count(*) FROM customers) AS customers, (SELECT count(*) FROM customers WHERE customer_type = 'Individual') AS individuals,
       (SELECT count(*) FROM customers WHERE customer_type = 'Business') AS business_custs,
       (SELECT round(sum(subtotal_amount) / 1e6, 2) FROM sales_orders WHERE status = 'Completed') AS revenue_m,
       (SELECT round(avg(subtotal_amount), 0) FROM sales_orders WHERE status = 'Completed') AS aov,
       ((SELECT count(*) FROM sales_orders) BETWEEN 108000 AND 132000
        AND (SELECT count(*) FROM sales_order_items) BETWEEN 270000 AND 330000
        AND (SELECT count(*) FROM customers WHERE customer_type = 'Individual') = 5988
        AND (SELECT count(*) FROM customers WHERE customer_type = 'Business') = 12
        AND (SELECT sum(subtotal_amount) FROM sales_orders WHERE status = 'Completed') BETWEEN 85e6 AND 95e6
        AND (SELECT avg(subtotal_amount) FROM sales_orders WHERE status = 'Completed') BETWEEN 700 AND 800) AS pass;

\echo '-- G-10 Growth'
WITH rev AS (SELECT extract(year FROM order_date)::int y, extract(month FROM order_date)::int m, subtotal_amount FROM sales_orders WHERE status = 'Completed')
SELECT round(100.0 * ((SELECT sum(subtotal_amount) FROM rev WHERE y = 2025) / (SELECT sum(subtotal_amount) FROM rev WHERE y = 2024) - 1), 2) AS g25_pct,
       round(100.0 * ((SELECT sum(subtotal_amount) FROM rev WHERE y = 2026 AND m <= 10) / (SELECT sum(subtotal_amount) FROM rev WHERE y = 2025 AND m <= 10) - 1), 2) AS g26_ytd_pct,
       (round(100.0 * ((SELECT sum(subtotal_amount) FROM rev WHERE y = 2025) / (SELECT sum(subtotal_amount) FROM rev WHERE y = 2024) - 1), 2) BETWEEN 10.5 AND 13.5
        AND round(100.0 * ((SELECT sum(subtotal_amount) FROM rev WHERE y = 2026 AND m <= 10) / (SELECT sum(subtotal_amount) FROM rev WHERE y = 2025 AND m <= 10) - 1), 2) BETWEEN 7.5 AND 10.5) AS pass;

\echo '-- G-11 Channel mix'
WITH g AS (SELECT extract(year FROM order_date)::int y,
                  CASE WHEN channel IN ('Online', 'Mobile App') THEN 'online' WHEN channel = 'B2B' THEN 'b2b' ELSE 'instore' END grp,
                  subtotal_amount FROM sales_orders WHERE status = 'Completed' AND (extract(year FROM order_date) < 2026 OR extract(month FROM order_date) <= 10))
SELECT y, round(100.0 * sum(subtotal_amount) FILTER (WHERE grp = 'online') / sum(subtotal_amount), 2) AS online_pct,
       round(100.0 * sum(subtotal_amount) FILTER (WHERE grp = 'b2b') / sum(subtotal_amount), 2) AS b2b_pct,
       round(100.0 * sum(subtotal_amount) FILTER (WHERE grp = 'instore') / sum(subtotal_amount), 2) AS instore_pct
FROM g GROUP BY y ORDER BY y;
WITH g AS (SELECT extract(year FROM order_date)::int y,
                  CASE WHEN channel IN ('Online', 'Mobile App') THEN 'online' WHEN channel = 'B2B' THEN 'b2b' ELSE 'instore' END grp,
                  subtotal_amount FROM sales_orders WHERE status = 'Completed' AND (extract(year FROM order_date) < 2026 OR extract(month FROM order_date) <= 10)),
     sh AS (SELECT y, round(100.0 * sum(subtotal_amount) FILTER (WHERE grp = 'online') / sum(subtotal_amount), 2) o,
                   round(100.0 * sum(subtotal_amount) FILTER (WHERE grp = 'b2b') / sum(subtotal_amount), 2) b FROM g GROUP BY y)
SELECT bool_and(CASE y WHEN 2024 THEN o BETWEEN 12.5 AND 15.5 WHEN 2025 THEN o BETWEEN 17.5 AND 20.5 WHEN 2026 THEN o BETWEEN 22.5 AND 25.5 END
                AND b BETWEEN 6.0 AND 9.0) AS pass FROM sh;

\echo '-- G-12 Store ranking (2025, excluding RYD-DC)'
WITH r AS (SELECT branch_id, sum(subtotal_amount) rev FROM sales_orders
           WHERE status = 'Completed' AND extract(year FROM order_date) = 2025 AND branch_id BETWEEN 1 AND 8 GROUP BY branch_id)
SELECT array_agg(branch_id ORDER BY rev DESC) AS ranking,
       (array_agg(branch_id ORDER BY rev DESC) = ARRAY[1,2,3,4,5,6,8,7]::int[]
        OR array_agg(branch_id ORDER BY rev DESC) = ARRAY[1,2,3,4,5,6,7,8]::int[]) AS rank_pass,
       round(100.0 * (SELECT rev FROM r WHERE branch_id = 5) / (SELECT rev FROM r WHERE branch_id = 4), 1) AS khb_pct_of_dmm,
       round(100.0 * ((SELECT rev FROM r WHERE branch_id = 7) / (SELECT rev FROM r WHERE branch_id = 8) - 1), 1) AS obh_vs_abh_pct
FROM r;
-- ABH-CTY (8) lowest store revenue in every year
SELECT y, (min(rev) = min(rev) FILTER (WHERE branch_id = 8)) AS abh_is_lowest
FROM (SELECT extract(year FROM order_date)::int y, branch_id, sum(subtotal_amount) rev FROM sales_orders
      WHERE status = 'Completed' AND branch_id BETWEEN 1 AND 8 GROUP BY 1, 2) s
GROUP BY y ORDER BY y;

\echo '-- G-13 Line ranking (revenue, units, margin) and realized-vs-target margin'
WITH it AS (SELECT i.*, p.category_id, o.order_date, o.status FROM sales_order_items i
            JOIN sales_orders o ON o.order_id = i.order_id JOIN products p ON p.product_id = i.product_id WHERE o.status = 'Completed'),
     yrs AS (SELECT 2024 y UNION SELECT 2025 UNION SELECT 2026)
SELECT yrs.y, c.category_code,
       sum(it.line_total) rev, rank() OVER (PARTITION BY yrs.y ORDER BY sum(it.line_total) DESC) rev_rank,
       sum(it.quantity) units, rank() OVER (PARTITION BY yrs.y ORDER BY sum(it.quantity) DESC) unit_rank
FROM yrs JOIN it ON extract(year FROM it.order_date) = yrs.y AND (yrs.y < 2026 OR extract(month FROM it.order_date) <= 10)
JOIN product_categories c ON c.category_id = it.category_id
GROUP BY yrs.y, c.category_code ORDER BY yrs.y, rev_rank;

WITH it AS (SELECT i.*, p.category_id FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id
            JOIN products p ON p.product_id = i.product_id WHERE o.status = 'Completed')
SELECT c.category_code, c.target_margin_pct,
       round(100.0 * (1 - sum(it.line_cost) / sum(it.line_total)), 2) AS realized_margin_pct,
       round(abs(100.0 * (1 - sum(it.line_cost) / sum(it.line_total)) - c.target_margin_pct), 2) AS abs_diff,
       (abs(100.0 * (1 - sum(it.line_cost) / sum(it.line_total)) - c.target_margin_pct) <= 2) AS pass
FROM it JOIN product_categories c ON c.category_id = it.category_id GROUP BY c.category_code, c.target_margin_pct ORDER BY 3 DESC;

\echo '=================================================================================================='
\echo 'SEASONALITY AND CALENDAR EFFECTS'
\echo '=================================================================================================='

\echo '-- G-14 Weekend uplift (Fri/Sat vs Sun-Thu, outside Ramadan), store channel only'
WITH d AS (SELECT o.order_date, cal.is_weekend, cal.is_ramadan, sum(o.subtotal_amount) rev
           FROM sales_orders o JOIN calendar cal ON cal.date_key = o.order_date
           WHERE o.status = 'Completed' AND o.channel = 'In-Store' AND NOT cal.is_ramadan GROUP BY 1, 2, 3)
SELECT round(avg(rev) FILTER (WHERE is_weekend), 0) AS avg_weekend, round(avg(rev) FILTER (WHERE NOT is_weekend), 0) AS avg_weekday,
       round(avg(rev) FILTER (WHERE is_weekend) / avg(rev) FILTER (WHERE NOT is_weekend), 3) AS ratio,
       (avg(rev) FILTER (WHERE is_weekend) / avg(rev) FILTER (WHERE NOT is_weekend) >= 1.20) AS pass FROM d;

\echo '-- G-15 Payday uplift (days 25-28 vs rest of month, outside event windows)'
WITH d AS (SELECT o.order_date, cal.is_payday, sum(o.subtotal_amount) rev
           FROM sales_orders o JOIN calendar cal ON cal.date_key = o.order_date
           WHERE o.status = 'Completed' AND o.channel = 'In-Store' AND cal.season = 'Regular' GROUP BY 1, 2)
SELECT round(avg(rev) FILTER (WHERE is_payday), 0) AS avg_payday, round(avg(rev) FILTER (WHERE NOT is_payday), 0) AS avg_other,
       round(avg(rev) FILTER (WHERE is_payday) / avg(rev) FILTER (WHERE NOT is_payday), 3) AS ratio,
       (avg(rev) FILTER (WHERE is_payday) / avg(rev) FILTER (WHERE NOT is_payday) >= 1.15) AS pass FROM d;

\echo '-- G-16 Ramadan grocery uplift, and Grocery peak month contains Ramadan'
WITH d AS (SELECT extract(year FROM o.order_date)::int y, cal.is_ramadan, o.order_date, i.line_total
           FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id JOIN products p ON p.product_id = i.product_id
           JOIN product_categories c ON c.category_id = p.category_id JOIN calendar cal ON cal.date_key = o.order_date
           WHERE o.status = 'Completed' AND c.category_code = 'GROC'),
     daily AS (SELECT y, is_ramadan, order_date, sum(line_total) rev FROM d GROUP BY 1, 2, 3)
SELECT y, round(avg(rev) FILTER (WHERE is_ramadan), 0) AS avg_ramadan, round(avg(rev) FILTER (WHERE NOT is_ramadan), 0) AS avg_regular,
       round(avg(rev) FILTER (WHERE is_ramadan) / avg(rev) FILTER (WHERE NOT is_ramadan), 2) AS ratio,
       (avg(rev) FILTER (WHERE is_ramadan) / avg(rev) FILTER (WHERE NOT is_ramadan) >= 1.4) AS pass FROM daily GROUP BY y ORDER BY y;

WITH d AS (SELECT extract(year FROM o.order_date)::int y, extract(month FROM o.order_date)::int m, i.line_total
           FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id JOIN products p ON p.product_id = i.product_id
           JOIN product_categories c ON c.category_id = p.category_id WHERE o.status = 'Completed' AND c.category_code = 'GROC'),
     monthly AS (SELECT y, m, sum(line_total) rev FROM d GROUP BY 1, 2),
     peak AS (SELECT y, m, rank() OVER (PARTITION BY y ORDER BY rev DESC) rk FROM monthly)
SELECT peak.y, peak.m AS peak_month,
       exists(SELECT 1 FROM calendar cal WHERE cal.is_ramadan AND extract(year FROM cal.date_key) = peak.y AND extract(month FROM cal.date_key) = peak.m) AS contains_ramadan
FROM peak WHERE rk = 1 ORDER BY peak.y;

\echo '-- G-17 White Friday uplift, Electronics share, Online+App share'
WITH d AS (SELECT extract(year FROM o.order_date)::int y, o.season, o.order_date, o.subtotal_amount, o.channel
           FROM sales_orders o WHERE o.status = 'Completed' AND o.channel = 'In-Store'),
     daily AS (SELECT y, (season = 'White Friday') wf, order_date, sum(subtotal_amount) rev FROM d GROUP BY 1, 2, 3)
SELECT y, round(avg(rev) FILTER (WHERE wf), 0) AS avg_wf, round(avg(rev) FILTER (WHERE NOT wf), 0) AS avg_regular,
       round(avg(rev) FILTER (WHERE wf) / avg(rev) FILTER (WHERE NOT wf), 2) AS ratio,
       (avg(rev) FILTER (WHERE wf) / avg(rev) FILTER (WHERE NOT wf) >= 1.8) AS pass
FROM daily WHERE y IN (2024, 2025) GROUP BY y ORDER BY y;

WITH base AS (SELECT o.order_id, (o.season = 'White Friday') wf, i.line_total, p.category_id
              FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id JOIN products p ON p.product_id = i.product_id
              WHERE o.status = 'Completed')
SELECT round(100.0 * sum(line_total) FILTER (WHERE wf AND category_id = (SELECT category_id FROM product_categories WHERE category_code = 'ELEC')) / sum(line_total) FILTER (WHERE wf), 2) AS elec_share_wf,
       round(100.0 * sum(line_total) FILTER (WHERE NOT wf AND category_id = (SELECT category_id FROM product_categories WHERE category_code = 'ELEC')) / sum(line_total) FILTER (WHERE NOT wf), 2) AS elec_share_regular,
       (round(100.0 * sum(line_total) FILTER (WHERE wf AND category_id = (SELECT category_id FROM product_categories WHERE category_code = 'ELEC')) / sum(line_total) FILTER (WHERE wf), 2)
        - round(100.0 * sum(line_total) FILTER (WHERE NOT wf AND category_id = (SELECT category_id FROM product_categories WHERE category_code = 'ELEC')) / sum(line_total) FILTER (WHERE NOT wf), 2) >= 5) AS pass
FROM base;
WITH o2 AS (SELECT (season = 'White Friday') wf, CASE WHEN channel IN ('Online', 'Mobile App') THEN 1 ELSE 0 END online, subtotal_amount
            FROM sales_orders WHERE status = 'Completed')
SELECT round(100.0 * sum(subtotal_amount) FILTER (WHERE wf AND online = 1) / sum(subtotal_amount) FILTER (WHERE wf), 2) AS online_share_wf,
       round(100.0 * sum(subtotal_amount) FILTER (WHERE NOT wf AND online = 1) / sum(subtotal_amount) FILTER (WHERE NOT wf), 2) AS online_share_regular,
       (sum(subtotal_amount) FILTER (WHERE wf AND online = 1) / sum(subtotal_amount) FILTER (WHERE wf)
        > sum(subtotal_amount) FILTER (WHERE NOT wf AND online = 1) / sum(subtotal_amount) FILTER (WHERE NOT wf)) AS pass
FROM o2;

\echo '-- G-18 Line/subcategory seasonality (units vs the SKUs own yearly monthly average; peak windows)'
WITH u AS (SELECT p.subcategory, extract(year FROM o.order_date)::int y, extract(month FROM o.order_date)::int m, sum(i.quantity) units
           FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id JOIN products p ON p.product_id = i.product_id
           WHERE o.status = 'Completed' GROUP BY 1, 2, 3)
SELECT 'Cooling and Fans Jun-Aug >=1.5x yearly monthly avg' AS rule, y,
       round(avg(units) FILTER (WHERE m IN (6,7,8)) / avg(units), 2) AS ratio,
       (avg(units) FILTER (WHERE m IN (6,7,8)) / avg(units) >= 1.5) AS pass
FROM u WHERE subcategory = 'Cooling and Fans' GROUP BY y
UNION ALL
SELECT 'Camping Gear Nov-Feb >=1.4x yearly monthly avg', y, round(avg(units) FILTER (WHERE m IN (11,12,1,2)) / avg(units), 2),
       (avg(units) FILTER (WHERE m IN (11,12,1,2)) / avg(units) >= 1.4)
FROM u WHERE subcategory = 'Camping Gear' GROUP BY y
UNION ALL
SELECT 'School Bags Aug1-Sep15 >=1.6x yearly monthly avg', y, round(avg(units) FILTER (WHERE (m = 8) OR (m = 9)) / avg(units), 2),
       (avg(units) FILTER (WHERE (m = 8) OR (m = 9)) / avg(units) >= 1.6)
FROM u WHERE subcategory = 'School Bags' GROUP BY y
ORDER BY 1, 2;

-- average daily units in the named event window vs. the category's own Regular-day average
WITH d AS (SELECT c.category_code, o.season, o.order_date, i.quantity FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id
           JOIN products p ON p.product_id = i.product_id JOIN product_categories c ON c.category_id = p.category_id WHERE o.status = 'Completed'),
     daily AS (SELECT category_code, season, order_date, sum(quantity) q FROM d GROUP BY 1,2,3)
SELECT 'FASH Eid al-Fitr vs Regular' AS rule,
       round(avg(q) FILTER (WHERE season = 'Eid al-Fitr') / avg(q) FILTER (WHERE season = 'Regular'), 2) AS ratio,
       (avg(q) FILTER (WHERE season = 'Eid al-Fitr') / avg(q) FILTER (WHERE season = 'Regular') >= 1.4) AS pass FROM daily WHERE category_code = 'FASH'
UNION ALL
SELECT 'BEAU Eid al-Fitr vs Regular', round(avg(q) FILTER (WHERE season = 'Eid al-Fitr') / avg(q) FILTER (WHERE season = 'Regular'), 2),
       (avg(q) FILTER (WHERE season = 'Eid al-Fitr') / avg(q) FILTER (WHERE season = 'Regular') >= 1.3) FROM daily WHERE category_code = 'BEAU'
UNION ALL
SELECT 'BEAU National Day vs Regular', round(avg(q) FILTER (WHERE season = 'National Day') / avg(q) FILTER (WHERE season = 'Regular'), 2),
       (avg(q) FILTER (WHERE season = 'National Day') / avg(q) FILTER (WHERE season = 'Regular') >= 1.3) FROM daily WHERE category_code = 'BEAU'
UNION ALL
SELECT 'HOME (Decor) White Friday vs Regular', round(avg(q) FILTER (WHERE season = 'White Friday') / avg(q) FILTER (WHERE season = 'Regular'), 2),
       (avg(q) FILTER (WHERE season = 'White Friday') / avg(q) FILTER (WHERE season = 'Regular') >= 1.3) FROM daily WHERE category_code = 'HOME';

\echo '-- G-19 Location effects: MED-QBA Ramadan+Hajj uplift vs chain uplift; ABH/JED-OBH summer uplift'
WITH d AS (SELECT o.branch_id, o.order_date, cal.season, cal.is_ramadan, o.subtotal_amount
           FROM sales_orders o JOIN calendar cal ON cal.date_key = o.order_date WHERE o.status = 'Completed' AND o.channel = 'In-Store'),
     daily AS (SELECT branch_id, order_date, bool_or(is_ramadan) OR bool_or(season = 'Hajj and Eid al-Adha') AS event, sum(subtotal_amount) rev FROM d GROUP BY 1, 2),
     up AS (SELECT branch_id, avg(rev) FILTER (WHERE event) / avg(rev) FILTER (WHERE NOT event) AS uplift FROM daily GROUP BY branch_id)
SELECT (SELECT uplift FROM up WHERE branch_id = 6) AS med_qba_uplift,
       (SELECT avg(uplift) FROM up WHERE branch_id BETWEEN 1 AND 8) AS chain_avg_uplift,
       round((SELECT uplift FROM up WHERE branch_id = 6) / (SELECT avg(uplift) FROM up WHERE branch_id BETWEEN 1 AND 8), 2) AS ratio,
       ((SELECT uplift FROM up WHERE branch_id = 6) / (SELECT avg(uplift) FROM up WHERE branch_id BETWEEN 1 AND 8) >= 1.2) AS pass;

WITH d AS (SELECT branch_id, extract(month FROM order_date)::int m, order_date, subtotal_amount FROM sales_orders WHERE status = 'Completed' AND channel = 'In-Store' AND branch_id IN (7, 8)),
     daily AS (SELECT branch_id, m, order_date, sum(subtotal_amount) rev FROM d GROUP BY 1, 2, 3)
SELECT branch_id, round(avg(rev) FILTER (WHERE m IN (6,7,8)) / avg(rev), 2) AS summer_vs_own_avg,
       (avg(rev) FILTER (WHERE m IN (6,7,8)) / avg(rev) >= 1.2) AS pass FROM daily GROUP BY branch_id ORDER BY branch_id;

\echo '=================================================================================================='
\echo 'CUSTOMERS AND STATISTICAL GROUND TRUTHS'
\echo '=================================================================================================='

\echo '-- G-20 Loyalty tiers: recomputed TTM tier vs stored; tier shares'
WITH ttm AS (SELECT customer_id, sum(subtotal_amount) spend FROM sales_orders
             WHERE status = 'Completed' AND order_date >= '2025-11-01' AND customer_id IS NOT NULL GROUP BY customer_id),
     recomputed AS (SELECT c.customer_id, c.customer_type, c.loyalty_tier stored,
                           CASE WHEN c.customer_type = 'Business' THEN 'None'
                                WHEN coalesce(t.spend, 0) >= 25000 THEN 'Platinum' WHEN coalesce(t.spend, 0) >= 10000 THEN 'Gold'
                                WHEN coalesce(t.spend, 0) >= 3000 THEN 'Silver' ELSE 'None' END AS recomputed
                    FROM customers c LEFT JOIN ttm t ON t.customer_id = c.customer_id)
SELECT count(*) FILTER (WHERE stored <> recomputed) AS mismatches, (count(*) FILTER (WHERE stored <> recomputed) = 0) AS pass FROM recomputed;
SELECT loyalty_tier, round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct FROM customers WHERE customer_type = 'Individual' GROUP BY loyalty_tier ORDER BY 1;

\echo '-- G-21 Tier value ordering; Gold vs Silver Welch t-test; ANOVA across tiers (2025 Completed, individuals)'
WITH c25 AS (SELECT c.loyalty_tier, o.subtotal_amount FROM sales_orders o JOIN customers c ON c.customer_id = o.customer_id
             WHERE o.status = 'Completed' AND extract(year FROM o.order_date) = 2025 AND c.customer_type = 'Individual')
SELECT loyalty_tier, round(avg(subtotal_amount), 1) AS aov, count(*) n FROM c25 GROUP BY loyalty_tier ORDER BY aov DESC;
WITH c25 AS (SELECT c.loyalty_tier, o.subtotal_amount FROM sales_orders o JOIN customers c ON c.customer_id = o.customer_id
             WHERE o.status = 'Completed' AND extract(year FROM o.order_date) = 2025 AND c.customer_type = 'Individual'),
     ord AS (SELECT array_agg(aov ORDER BY ord) a FROM (SELECT avg(subtotal_amount) aov, CASE loyalty_tier WHEN 'Platinum' THEN 1 WHEN 'Gold' THEN 2 WHEN 'Silver' THEN 3 ELSE 4 END ord FROM c25 GROUP BY loyalty_tier) s),
     g AS (SELECT array_agg(subtotal_amount) s FROM c25 WHERE loyalty_tier = 'Gold'),
     s AS (SELECT array_agg(subtotal_amount) s FROM c25 WHERE loyalty_tier = 'Silver'),
     w AS (SELECT * FROM verify.welch((SELECT s FROM g), (SELECT s FROM s)))
SELECT (SELECT a[1] > a[2] AND a[2] > a[3] AND a[3] > a[4] FROM ord) AS aov_order_pass,
       round(w.t::numeric, 3) AS gold_silver_t, round(w.df::numeric, 1) AS gold_silver_df, w.p AS gold_silver_p, (w.p < 0.05) AS gold_silver_pass
FROM w;
WITH c25 AS (SELECT c.loyalty_tier, o.subtotal_amount FROM sales_orders o JOIN customers c ON c.customer_id = o.customer_id
             WHERE o.status = 'Completed' AND extract(year FROM o.order_date) = 2025 AND c.customer_type = 'Individual'),
     grp AS (SELECT loyalty_tier, count(*) n, avg(subtotal_amount) m, variance(subtotal_amount) v FROM c25 GROUP BY loyalty_tier),
     overall AS (SELECT avg(subtotal_amount) gm, count(*) gn FROM c25),
     ssb AS (SELECT sum(n * (m - (SELECT gm FROM overall)) ^ 2) AS val, count(*) k FROM grp),
     ssw AS (SELECT sum((n - 1) * v) AS val FROM grp)
SELECT round((ssb.val / (ssb.k - 1)) / (ssw.val / ((SELECT gn FROM overall) - ssb.k)), 2) AS f_stat,
       verify.f_p((ssb.val / (ssb.k - 1)) / (ssw.val / ((SELECT gn FROM overall) - ssb.k)), ssb.k - 1, (SELECT gn FROM overall) - ssb.k) AS anova_p,
       (verify.f_p((ssb.val / (ssb.k - 1)) / (ssw.val / ((SELECT gn FROM overall) - ssb.k)), ssb.k - 1, (SELECT gn FROM overall) - ssb.k) < 0.001) AS pass
FROM ssb, ssw;

\echo '-- G-22 Customer base: registrations, repeat rate, cohort re-order, acquisition channels'
SELECT min(registration_date) AS first_reg, max(registration_date) AS last_reg FROM customers WHERE customer_type = 'Individual';
SELECT y, min(n) AS min_monthly_regs, (min(n) >= 100) AS pass FROM (
  SELECT extract(year FROM registration_date)::int y, extract(month FROM registration_date)::int m, count(*) n
  FROM customers WHERE customer_type = 'Individual' AND extract(year FROM registration_date) IN (2025, 2026) GROUP BY 1, 2) s
GROUP BY y ORDER BY y;
WITH per_cust AS (SELECT o.customer_id, count(*) n FROM sales_orders o JOIN customers c ON c.customer_id = o.customer_id
                  WHERE o.status = 'Completed' AND extract(year FROM o.order_date) = 2025 AND c.customer_type = 'Individual' GROUP BY o.customer_id)
SELECT round(100.0 * count(*) FILTER (WHERE n >= 2) / count(*), 2) AS repeat_pct,
       (round(100.0 * count(*) FILTER (WHERE n >= 2) / count(*), 2) BETWEEN 30 AND 45) AS pass FROM per_cust;
WITH reg AS (SELECT customer_id, date_trunc('month', registration_date) m0 FROM customers
             WHERE customer_type = 'Individual' AND extract(year FROM registration_date) = 2025),
     oc AS (SELECT customer_id, date_trunc('month', order_date) om FROM sales_orders WHERE status = 'Completed' AND customer_id IS NOT NULL),
     j AS (SELECT reg.customer_id, reg.m0, (extract(year FROM oc.om) - extract(year FROM reg.m0)) * 12 + (extract(month FROM oc.om) - extract(month FROM reg.m0)) AS k
           FROM reg JOIN oc ON oc.customer_id = reg.customer_id),
     retained AS (SELECT DISTINCT customer_id FROM j WHERE k BETWEEN 1 AND 3)
SELECT min(rr) AS min_cohort_pct, max(rr) AS max_cohort_pct, (min(rr) BETWEEN 25 AND 40 AND max(rr) BETWEEN 25 AND 40) AS pass FROM (
  SELECT reg.m0, round(100.0 * count(*) FILTER (WHERE reg.customer_id IN (SELECT customer_id FROM retained)) / count(*), 2) rr
  FROM reg GROUP BY reg.m0) s;
SELECT array_agg(DISTINCT acquisition_channel ORDER BY acquisition_channel) AS channels,
       (ARRAY['In-Store','Online','Mobile App','Referral','Social Media']::varchar[] <@ array_agg(DISTINCT acquisition_channel)
        OR ARRAY['Walk-in','Website','Mobile App','Referral','Social Media']::varchar[] <@ array_agg(DISTINCT acquisition_channel)) AS pass
FROM customers WHERE customer_type = 'Individual';

\echo '-- G-23 Online+App vs In-Store AOV (2025 Completed), Welch t-test'
WITH c25 AS (SELECT CASE WHEN channel IN ('Online', 'Mobile App') THEN 'online' ELSE 'instore' END grp, subtotal_amount
             FROM sales_orders WHERE status = 'Completed' AND extract(year FROM order_date) = 2025 AND channel <> 'B2B'),
     on_a AS (SELECT array_agg(subtotal_amount) a FROM c25 WHERE grp = 'online'),
     in_a AS (SELECT array_agg(subtotal_amount) a FROM c25 WHERE grp = 'instore'),
     w AS (SELECT * FROM verify.welch((SELECT a FROM on_a), (SELECT a FROM in_a)))
SELECT round((SELECT avg(x) FROM unnest((SELECT a FROM on_a)) x), 1) AS online_aov,
       round((SELECT avg(x) FROM unnest((SELECT a FROM in_a)) x), 1) AS instore_aov,
       round(100.0 * ((SELECT avg(x) FROM unnest((SELECT a FROM on_a)) x) / (SELECT avg(x) FROM unnest((SELECT a FROM in_a)) x) - 1), 1) AS uplift_pct,
       w.p AS welch_p,
       ((SELECT avg(x) FROM unnest((SELECT a FROM on_a)) x) / (SELECT avg(x) FROM unnest((SELECT a FROM in_a)) x) - 1 >= 0.15 AND w.p < 0.01) AS pass
FROM w;

\echo '-- G-24 DMM vs KHB AOV (2025 Completed), null-result Welch t-test'
WITH c25 AS (SELECT branch_id, subtotal_amount FROM sales_orders WHERE status = 'Completed' AND extract(year FROM order_date) = 2025 AND branch_id IN (4, 5)),
     dmm AS (SELECT array_agg(subtotal_amount) a FROM c25 WHERE branch_id = 4),
     khb AS (SELECT array_agg(subtotal_amount) a FROM c25 WHERE branch_id = 5),
     w AS (SELECT * FROM verify.welch((SELECT a FROM dmm), (SELECT a FROM khb)))
SELECT round(100.0 * abs((SELECT avg(x) FROM unnest((SELECT a FROM khb)) x) / (SELECT avg(x) FROM unnest((SELECT a FROM dmm)) x) - 1), 3) AS pct_diff,
       w.p AS welch_p,
       (round(100.0 * abs((SELECT avg(x) FROM unnest((SELECT a FROM khb)) x) / (SELECT avg(x) FROM unnest((SELECT a FROM dmm)) x) - 1), 3) < 2 AND w.p > 0.10) AS pass
FROM w;

\echo '-- G-25 Promotion effect on AOV; discount_pct vs quantity Spearman correlation'
WITH c25 AS (SELECT (promotion_id IS NOT NULL) has_promo, subtotal_amount FROM sales_orders WHERE status = 'Completed' AND extract(year FROM order_date) = 2025),
     p_a AS (SELECT array_agg(subtotal_amount) a FROM c25 WHERE has_promo),
     np_a AS (SELECT array_agg(subtotal_amount) a FROM c25 WHERE NOT has_promo),
     w AS (SELECT * FROM verify.welch((SELECT a FROM p_a), (SELECT a FROM np_a)))
SELECT w.p AS welch_p, (w.p < 0.01) AS pass FROM w;
WITH it AS (SELECT i.discount_pct, i.quantity FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id
            WHERE o.status = 'Completed' AND extract(year FROM o.order_date) = 2025),
     ranks AS (SELECT rank() OVER (ORDER BY discount_pct) rx, rank() OVER (ORDER BY quantity) ry FROM it),
     n AS (SELECT count(*) n FROM ranks),
     corr AS (SELECT corr(rx, ry) r FROM ranks)
SELECT round(corr.r::numeric, 3) AS spearman_r,
       verify.t_p2(corr.r * sqrt(((SELECT n FROM n) - 2) / (1 - corr.r ^ 2)), (SELECT n FROM n) - 2) AS spearman_p,
       (corr.r BETWEEN 0.15 AND 0.40 AND verify.t_p2(corr.r * sqrt(((SELECT n FROM n) - 2) / (1 - corr.r ^ 2)), (SELECT n FROM n) - 2) < 0.001) AS pass
FROM corr;

\echo '-- G-26 Payment x channel (chi-square); Fashion vs Grocery return rate (two-prop z); weekend vs weekday (Welch)'
WITH obs AS (SELECT payment_method, channel, count(*) n FROM sales_orders GROUP BY 1, 2),
     rowt AS (SELECT payment_method, sum(n) rt FROM obs GROUP BY 1),
     colt AS (SELECT channel, sum(n) ct FROM obs GROUP BY 1),
     tot AS (SELECT sum(n) gt FROM obs),
     chi AS (SELECT sum((o.n - r.rt * c.ct / t.gt) ^ 2 / (r.rt * c.ct / t.gt)) x2,
                    (count(DISTINCT o.payment_method) - 1) * (count(DISTINCT o.channel) - 1) df
             FROM obs o JOIN rowt r ON r.payment_method = o.payment_method JOIN colt c ON c.channel = o.channel, tot t)
SELECT round(x2, 1) AS chi2, df, verify.chi2_p(x2, df) AS p, (verify.chi2_p(x2, df) < 0.001) AS pass FROM chi;

WITH r AS (SELECT c.category_code,
                  count(DISTINCT sr.order_item_id) FILTER (WHERE TRUE) AS returned_lines,
                  (SELECT count(*) FROM sales_order_items i2 JOIN sales_orders o2 ON o2.order_id = i2.order_id JOIN products p2 ON p2.product_id = i2.product_id
                   WHERE p2.category_id = p.category_id AND o2.status = 'Completed') AS total_lines
           FROM sales_returns sr JOIN sales_order_items i ON i.order_item_id = sr.order_item_id JOIN products p ON p.product_id = i.product_id
           JOIN product_categories c ON c.category_id = p.category_id WHERE c.category_code IN ('FASH', 'GROC') GROUP BY c.category_code, p.category_id),
     agg AS (SELECT category_code, sum(returned_lines) x, max(total_lines) n FROM r GROUP BY category_code),
     f AS (SELECT x, n FROM agg WHERE category_code = 'FASH'), g AS (SELECT x, n FROM agg WHERE category_code = 'GROC'),
     pooled AS (SELECT (f.x + g.x)::numeric / (f.n + g.n) pp FROM f, g)
SELECT round(100.0 * f.x / f.n, 2) AS fash_return_rate_pct, round(100.0 * g.x / g.n, 2) AS groc_return_rate_pct,
       2 * (1 - verify.norm_cdf(abs((f.x::numeric / f.n - g.x::numeric / g.n) / sqrt(pooled.pp * (1 - pooled.pp) * (1.0 / f.n + 1.0 / g.n))))) AS z_p,
       (2 * (1 - verify.norm_cdf(abs((f.x::numeric / f.n - g.x::numeric / g.n) / sqrt(pooled.pp * (1 - pooled.pp) * (1.0 / f.n + 1.0 / g.n)))))) < 0.001 AS pass
FROM f, g, pooled;

WITH d AS (SELECT branch_id, order_date, cal.is_weekend, sum(subtotal_amount) rev FROM sales_orders o JOIN calendar cal ON cal.date_key = o.order_date
           WHERE o.status = 'Completed' AND o.channel = 'In-Store' GROUP BY 1, 2, 3),
     we AS (SELECT array_agg(rev) a FROM d WHERE is_weekend), wd AS (SELECT array_agg(rev) a FROM d WHERE NOT is_weekend),
     w AS (SELECT * FROM verify.welch((SELECT a FROM we), (SELECT a FROM wd)))
SELECT w.p AS welch_p, (w.p < 0.001) AS pass FROM w;

\echo '=================================================================================================='
\echo 'RETURNS, PROMOTIONS AND TARGETS'
\echo '=================================================================================================='

\echo '-- G-27 Returns'
WITH itc AS (SELECT i.* FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id WHERE o.status = 'Completed')
SELECT round(100.0 * (SELECT sum(refund_amount) FROM sales_returns) / (SELECT sum(line_total) FROM itc), 2) AS overall_return_pct,
       ((SELECT sum(refund_amount) FROM sales_returns) / (SELECT sum(line_total) FROM itc) BETWEEN 0.03 AND 0.05) AS pass;
WITH itc AS (SELECT i.*, p.category_id FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id
             JOIN products p ON p.product_id = i.product_id WHERE o.status = 'Completed'),
     bycat AS (SELECT c.category_code, sum(sr.refund_amount) ref, sum(itc.line_total) tot
               FROM itc JOIN product_categories c ON c.category_id = itc.category_id
               LEFT JOIN sales_returns sr ON sr.order_item_id = itc.order_item_id GROUP BY c.category_code)
SELECT category_code, round(100.0 * ref / tot, 2) AS return_pct FROM bycat ORDER BY return_pct DESC;
SELECT round(100.0 * count(*) FILTER (WHERE return_reason = 'Defective') / count(*), 2) AS defective_pct_of_returns,
       (round(100.0 * count(*) FILTER (WHERE return_reason = 'Defective') / count(*), 2) BETWEEN 15 AND 25) AS pass FROM sales_returns;
SELECT count(*) AS window_violations,
       (count(*) FILTER (WHERE return_reason = 'Defective' AND return_date - (SELECT order_date FROM sales_orders WHERE order_id = sales_returns.order_id) > 30) +
        count(*) FILTER (WHERE return_reason <> 'Defective' AND return_date - (SELECT order_date FROM sales_orders WHERE order_id = sales_returns.order_id) > 14)) = 0 AS pass
FROM sales_returns;
SELECT count(*) AS restocked_violations, (count(*) = 0) AS pass FROM sales_returns WHERE return_reason IN ('Defective', 'Damaged in Transit') AND restocked;
SELECT array_agg(DISTINCT return_reason ORDER BY return_reason) AS reasons_present,
       (count(DISTINCT return_reason) = 6) AS pass FROM sales_returns;

\echo '-- G-28 Promotions: count, event alignment, caps, share of orders'
SELECT count(*) AS n_promos, (count(*) BETWEEN 30 AND 50) AS pass FROM promotions;
SELECT round(100.0 * count(*) FILTER (WHERE promotion_id IS NOT NULL) / count(*), 2) AS promo_order_pct,
       (round(100.0 * count(*) FILTER (WHERE promotion_id IS NOT NULL) / count(*), 2) BETWEEN 18 AND 26) AS pass FROM sales_orders;
WITH caps AS (SELECT * FROM (VALUES ('ELEC',25),('APPL',25),('FASH',50),('GROC',20),('BEAU',30),('SPRT',40),('KIDS',35),('HOME',40)) c(code, cap))
SELECT count(*) AS line_cap_violations, (count(*) = 0) AS pass
FROM sales_order_items i JOIN products p ON p.product_id = i.product_id JOIN product_categories pc ON pc.category_id = p.category_id
JOIN caps ON caps.code = pc.category_code WHERE i.discount_pct > caps.cap;
WITH caps AS (SELECT * FROM (VALUES ('ELEC',25),('APPL',25),('FASH',50),('GROC',20),('BEAU',30),('SPRT',40),('KIDS',35),('HOME',40)) c(code, cap))
SELECT count(*) AS promo_cap_violations, (count(*) = 0) AS pass
FROM promotions pr JOIN product_categories pc ON pc.category_id = pr.category_id JOIN caps ON caps.code = pc.category_code
WHERE pr.discount_pct > caps.cap;

\echo '-- G-29 Sales targets'
SELECT count(*) AS target_rows, (count(*) = 306) AS pass FROM monthly_sales_targets;
WITH t AS (SELECT branch_id, extract(year FROM target_month)::int y, extract(month FROM target_month)::int m, target_revenue FROM monthly_sales_targets),
     prior AS (SELECT a.branch_id, a.y, a.m, a.target_revenue cur, b.target_revenue prev
               FROM t a JOIN t b ON b.branch_id = a.branch_id AND b.y = a.y - 1 AND b.m = a.m WHERE a.y IN (2025, 2026))
SELECT count(*) AS ratio_violations, (count(*) = 0) AS pass FROM prior WHERE abs(cur / prev - 1.10) > 0.0005;
WITH rev AS (SELECT branch_id, date_trunc('month', order_date)::date ym, sum(subtotal_amount) rev FROM sales_orders WHERE status = 'Completed' GROUP BY 1, 2),
     att AS (SELECT t.branch_id, t.target_month, t.target_revenue, coalesce(r.rev, 0) / t.target_revenue AS a FROM monthly_sales_targets t LEFT JOIN rev r ON r.branch_id = t.branch_id AND r.ym = t.target_month)
SELECT count(*) FILTER (WHERE a < 0.8 OR a > 1.2) AS out_of_80_120, count(*) FILTER (WHERE a < 0.9) AS below_90, count(*) FILTER (WHERE a > 1.1) AS above_110,
       (count(*) FILTER (WHERE a < 0.8 OR a > 1.2) = 0 AND count(*) FILTER (WHERE a < 0.9) >= 8 AND count(*) FILTER (WHERE a > 1.1) >= 8) AS pass
FROM att;
WITH rev AS (SELECT branch_id, date_trunc('month', order_date)::date ym, sum(subtotal_amount) rev FROM sales_orders WHERE status = 'Completed' GROUP BY 1, 2),
     att AS (SELECT t.branch_id, coalesce(r.rev, 0) / t.target_revenue AS a FROM monthly_sales_targets t LEFT JOIN rev r ON r.branch_id = t.branch_id AND r.ym = t.target_month WHERE t.target_month = '2026-10-01')
SELECT count(*) FILTER (WHERE a < 1.0) AS oct26_miss, count(*) FILTER (WHERE a >= 1.0) AS oct26_meet,
       (count(*) FILTER (WHERE a < 1.0) >= 2 AND count(*) FILTER (WHERE a >= 1.0) >= 2) AS pass FROM att;

\echo '=================================================================================================='
\echo 'INVENTORY AND SUPPLIERS'
\echo '=================================================================================================='

\echo '-- G-30 Stock positions'
SELECT count(*) FILTER (WHERE branch_id = 9) AS dc_rows, count(*) AS total_rows,
       (count(*) FILTER (WHERE branch_id = 9) = 120) AS dc_pass FROM inventory_levels;
SELECT branch_id, count(*) AS skus FROM inventory_levels WHERE branch_id BETWEEN 1 AND 8 GROUP BY branch_id ORDER BY branch_id;
SELECT count(*) AS total_rows,
       count(*) FILTER (WHERE reorder_point < safety_stock) AS rop_below_ss,
       count(*) FILTER (WHERE max_stock_level <> reorder_point + reorder_quantity) AS max_mismatch,
       count(*) FILTER (WHERE quantity_on_hand - quantity_reserved <> (SELECT quantity_on_hand - quantity_reserved)) AS unused,
       count(*) FILTER (WHERE snapshot_date <> '2026-10-31') AS bad_snapshot_date,
       (count(*) FILTER (WHERE reorder_point < safety_stock) = 0 AND count(*) FILTER (WHERE max_stock_level <> reorder_point + reorder_quantity) = 0
        AND count(*) FILTER (WHERE snapshot_date <> '2026-10-31') = 0) AS pass
FROM inventory_levels;

\echo '-- G-31 Status mix via v_inventory_status'
SELECT stock_status, count(*) FROM v_inventory_status GROUP BY stock_status ORDER BY 2 DESC;
SELECT count(*) FILTER (WHERE stock_status IN ('Critical', 'Reorder Now')) AS crit_or_reorder,
       count(*) FILTER (WHERE stock_status = 'Out of Stock') AS oos,
       count(*) FILTER (WHERE stock_status = 'Overstock') AS overstock,
       count(*) FILTER (WHERE stock_status = 'Healthy') * 1.0 / count(*) AS healthy_frac,
       (SELECT count(*) FROM v_inventory_status WHERE lifecycle_status = 'Discontinued' AND quantity_on_hand > 0) AS discontinued_with_stock,
       (count(*) FILTER (WHERE stock_status IN ('Critical', 'Reorder Now')) >= 15
        AND count(*) FILTER (WHERE stock_status = 'Out of Stock') >= 5
        AND count(*) FILTER (WHERE stock_status = 'Overstock') >= 10
        AND count(*) FILTER (WHERE stock_status = 'Healthy') * 1.0 / count(*) >= 0.60
        AND (SELECT count(*) FROM v_inventory_status WHERE lifecycle_status = 'Discontinued' AND quantity_on_hand > 0) >= 3) AS pass
FROM v_inventory_status;

\echo '-- G-32 Lifecycle: new 2026 SKUs with <26 weeks of sales; discontinued SKUs; dead stock Aug-Oct 2026'
WITH new26 AS (SELECT product_id, sku FROM products WHERE launch_date BETWEEN '2026-03-01' AND '2026-07-31')
SELECT n.sku,
       (SELECT count(DISTINCT date_trunc('week', o.order_date)) FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id
        WHERE i.product_id = n.product_id AND o.status = 'Completed') AS weeks_of_sales
FROM new26 n ORDER BY n.sku;
WITH new26 AS (SELECT product_id FROM products WHERE launch_date BETWEEN '2026-03-01' AND '2026-07-31')
SELECT count(*) AS new_2026_skus,
       count(*) FILTER (WHERE (SELECT count(DISTINCT date_trunc('week', o.order_date)) FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id
                                WHERE i.product_id = new26.product_id AND o.status = 'Completed') < 26) AS with_lt_26_weeks,
       (count(*) >= 3 AND count(*) FILTER (WHERE (SELECT count(DISTINCT date_trunc('week', o.order_date)) FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id
                                WHERE i.product_id = new26.product_id AND o.status = 'Completed') < 26) >= 3) AS pass
FROM new26;
SELECT count(*) AS discontinued_skus, (count(*) >= 3) AS pass FROM products WHERE lifecycle_status = 'Discontinued';
WITH stock AS (SELECT product_id, sum(quantity_on_hand) oh FROM inventory_levels GROUP BY product_id),
     sold AS (SELECT DISTINCT i.product_id FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id
              WHERE o.status = 'Completed' AND o.order_date BETWEEN '2026-08-03' AND '2026-10-31')
SELECT count(*) AS dead_stock_skus, (count(*) >= 5) AS pass FROM stock WHERE oh > 0 AND product_id NOT IN (SELECT product_id FROM sold);

\echo '-- G-33 Stockouts at RYD-DC in 2025'
SELECT count(*) AS skus_with_3plus_stockout_weeks, (count(*) >= 12) AS pass FROM (
  SELECT product_id FROM inventory_snapshots WHERE branch_id = 9 AND stockout_days > 0 AND snapshot_date BETWEEN '2025-01-01' AND '2025-12-31'
  GROUP BY product_id HAVING count(*) >= 3) s;
SELECT count(*) AS out_of_range_stockout_days, (count(*) = 0) AS pass FROM inventory_snapshots WHERE stockout_days < 0 OR stockout_days > 7;
WITH full_out AS (SELECT branch_id, product_id, snapshot_date FROM inventory_snapshots WHERE stockout_days = 7),
     weekly_sales AS (SELECT o.branch_id, i.product_id, date_trunc('week', o.order_date) + interval '6 day' AS wk_sat, sum(i.quantity) q
                       FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id WHERE o.status = 'Completed' GROUP BY 1, 2, 3)
SELECT count(*) AS full_stockout_weeks_with_sales, (count(*) = 0) AS pass
FROM full_out f JOIN weekly_sales w ON w.branch_id = f.branch_id AND w.product_id = f.product_id AND w.wk_sat::date = f.snapshot_date;

\echo '-- G-34 Snapshot consistency'
SELECT min(snapshot_date), max(snapshot_date) FROM inventory_snapshots;
WITH per_series AS (SELECT branch_id, product_id, count(*) n FROM inventory_snapshots GROUP BY 1, 2)
SELECT count(*) FILTER (WHERE n = 148) AS series_with_148, count(*) AS total_series, max(n) AS max_snapshots, (max(n) <= 148) AS pass FROM per_series;
WITH last_snap AS (SELECT branch_id, product_id, quantity_on_hand FROM inventory_snapshots WHERE snapshot_date = '2026-10-31')
SELECT count(*) AS mismatches, (count(*) = 0) AS pass FROM last_snap s JOIN inventory_levels l ON l.branch_id = s.branch_id AND l.product_id = s.product_id
WHERE s.quantity_on_hand <> l.quantity_on_hand;
SELECT count(*) AS negative_snapshots, (count(*) = 0) AS pass FROM inventory_snapshots WHERE quantity_on_hand < 0;

\echo '-- G-35 Supplier on-time delivery'
WITH rec AS (SELECT supplier_id, (actual_delivery_date > expected_delivery_date) AS late FROM purchase_orders WHERE status IN ('Received', 'Partially Received')),
     meas AS (SELECT supplier_id, round(100.0 * (1 - avg(late::int)), 2) AS measured_pct FROM rec GROUP BY supplier_id)
SELECT s.supplier_code, s.on_time_delivery_pct AS registry_pct, m.measured_pct, round(abs(m.measured_pct - s.on_time_delivery_pct), 2) AS abs_diff,
       (abs(m.measured_pct - s.on_time_delivery_pct) <= 3) AS pass
FROM suppliers s JOIN meas m ON m.supplier_id = s.supplier_id ORDER BY abs_diff DESC;
SELECT count(*) FILTER (WHERE on_time_delivery_pct < 85) AS below_85, count(*) FILTER (WHERE on_time_delivery_pct < 90) AS below_90 FROM suppliers;

\echo '-- G-36 Purchase orders'
SELECT count(*) AS lead_time_mismatches, (count(*) = 0) AS pass FROM purchase_orders po JOIN suppliers s ON s.supplier_id = po.supplier_id
WHERE po.expected_delivery_date <> po.order_date + s.lead_time_days;
SELECT count(*) FILTER (WHERE status = 'Received' AND actual_delivery_date IS NULL) AS received_without_date,
       count(*) FILTER (WHERE status IN ('Open', 'In Transit') AND actual_delivery_date IS NOT NULL) AS open_with_date,
       count(*) FILTER (WHERE status IN ('Open', 'In Transit')) AS open_or_transit,
       (count(*) FILTER (WHERE status = 'Received' AND actual_delivery_date IS NULL) = 0
        AND count(*) FILTER (WHERE status IN ('Open', 'In Transit') AND actual_delivery_date IS NOT NULL) = 0
        AND count(*) FILTER (WHERE status IN ('Open', 'In Transit')) >= 40) AS pass
FROM purchase_orders;
SELECT count(*) AS qty_received_exceeds_ordered, (count(*) = 0) AS pass FROM purchase_order_items WHERE quantity_received > quantity_ordered;
SELECT count(*) AS below_moq_lines, (count(*) = 0) AS pass FROM purchase_order_items i JOIN purchase_orders po ON po.po_id = i.po_id
JOIN suppliers s ON s.supplier_id = po.supplier_id WHERE i.quantity_ordered < s.min_order_qty;
WITH tot AS (SELECT po_id, sum(quantity_ordered * unit_cost) t FROM purchase_order_items GROUP BY po_id)
SELECT count(*) AS total_amount_mismatches, (count(*) = 0) AS pass FROM purchase_orders po JOIN tot ON tot.po_id = po.po_id WHERE abs(po.total_amount - tot.t) > 0.01;

\echo '-- G-37 Stock adjustments'
SELECT count(*) AS n_adjustments, (count(*) BETWEEN 2000 AND 4000) AS pass FROM stock_adjustments;
SELECT reason, count(*) FROM stock_adjustments GROUP BY reason ORDER BY 2 DESC;
SELECT count(*) AS expiry_without_shelf_life, (count(*) = 0) AS pass FROM stock_adjustments sa JOIN products p ON p.product_id = sa.product_id
WHERE sa.reason = 'Expiry' AND p.shelf_life_days IS NULL;
WITH chk AS (SELECT sa.*, p.unit_cost FROM stock_adjustments sa JOIN products p ON p.product_id = sa.product_id)
SELECT count(*) AS cost_impact_mismatches, (count(*) = 0) AS pass FROM chk WHERE abs(cost_impact - round(quantity_change * unit_cost, 2)) > 0.01;

\echo '-- G-38 Forecastability'
WITH wk AS (SELECT i.product_id, date_trunc('week', o.order_date) wk, sum(i.quantity) q FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id
            WHERE o.status = 'Completed' GROUP BY 1, 2),
     span AS (SELECT product_id, count(*) n_weeks_with_sales,
                     (extract(epoch FROM (max(wk) - min(wk))) / 604800 + 1) AS n_weeks_span FROM wk GROUP BY product_id),
     per_sku AS (SELECT product_id, n_weeks_with_sales, n_weeks_span,
                        1 - n_weeks_with_sales / n_weeks_span AS zero_week_frac FROM span WHERE n_weeks_span >= 52)
SELECT count(*) AS skus_52plus_weeks_span, count(*) FILTER (WHERE zero_week_frac < 0.40) AS qualifying,
       (count(*) FILTER (WHERE zero_week_frac < 0.40) >= 90) AS pass FROM per_sku;
WITH wk AS (SELECT i.product_id, date_trunc('week', o.order_date) wk, sum(i.quantity) q FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id
            WHERE o.status = 'Completed' GROUP BY 1, 2),
     stat AS (SELECT product_id, avg(q) m, stddev(q) sd FROM wk GROUP BY product_id HAVING avg(q) > 0)
SELECT round(min(sd / m), 3) AS min_cv, round(max(sd / m), 3) AS max_cv,
       round(100.0 * count(*) FILTER (WHERE sd / m BETWEEN 0.15 AND 0.6) / count(*), 1) AS pct_in_band FROM stat;

\echo '=================================================================================================='
\echo 'DATA DEPENDENCIES (docs/06_evaluation_plan.md section 12)'
\echo '=================================================================================================='

\echo '-- DD-1/DD-2 JED-THL (branch 2) carries APPL-0002 and ELEC-0001, with sales history for APPL-0002'
SELECT p.sku,
       exists(SELECT 1 FROM inventory_levels l WHERE l.branch_id = 2 AND l.product_id = p.product_id) AS has_stock_position,
       (SELECT count(*) FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id
        WHERE o.branch_id = 2 AND i.product_id = p.product_id AND o.status = 'Completed') AS completed_sales_lines
FROM products p WHERE p.sku IN ('APPL-0002', 'ELEC-0001') ORDER BY p.sku;

\echo '-- DD-3 CUST-9999 does not exist'
SELECT count(*) AS matches, (count(*) = 0) AS pass FROM customers WHERE customer_code = 'CUST-9999';

\echo '-- DD-4 the six dead-stock SKUs have stock and no Completed sale 2026-08-03..2026-10-31'
WITH dead(sku) AS (VALUES ('ELEC-0013'), ('FASH-0014'), ('SPRT-0014'), ('HOME-0014'), ('FASH-0013'), ('HOME-0013'))
SELECT d.sku,
       (SELECT coalesce(sum(l.quantity_on_hand), 0) FROM inventory_levels l JOIN products p ON p.product_id = l.product_id WHERE p.sku = d.sku) AS total_stock,
       (SELECT count(*) FROM sales_order_items i JOIN sales_orders o ON o.order_id = i.order_id JOIN products p ON p.product_id = i.product_id
        WHERE p.sku = d.sku AND o.status = 'Completed' AND o.order_date BETWEEN '2026-08-03' AND '2026-10-31') AS completed_sales_in_window
FROM dead d ORDER BY d.sku;

\echo '-- DD-5 ELEC-0015 has 20-25 weeks of sales'
SELECT p.sku, count(DISTINCT date_trunc('week', o.order_date)) AS weeks_of_sales,
       (count(DISTINCT date_trunc('week', o.order_date)) BETWEEN 20 AND 25) AS pass
FROM products p JOIN sales_order_items i ON i.product_id = p.product_id JOIN sales_orders o ON o.order_id = i.order_id
WHERE p.sku = 'ELEC-0015' AND o.status = 'Completed' GROUP BY p.sku;

\echo '-- DD-6 Online/Mobile App orders carry a varied order time (not all midnight / not constant)'
SELECT channel, count(DISTINCT order_hour) AS distinct_hours, min(order_hour) AS min_h, max(order_hour) AS max_h,
       (count(DISTINCT order_hour) > 5) AS pass
FROM sales_orders WHERE channel IN ('Online', 'Mobile App') GROUP BY channel;

\echo '-- DD-7 at least one SKU has stockout weeks in 2025 at RYD-DC (subset of G-33)'
SELECT count(DISTINCT product_id) AS skus_with_any_stockout_2025_dc, (count(DISTINCT product_id) >= 1) AS pass
FROM inventory_snapshots WHERE branch_id = 9 AND stockout_days > 0 AND snapshot_date BETWEEN '2025-01-01' AND '2025-12-31';

\echo '=================================================================================================='
\echo 'End of verification. No data was changed -- rolling back the helper schema now.'
\echo '=================================================================================================='
ROLLBACK;
