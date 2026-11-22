-- Read-only role and grants (docs/03_database_design.md section 7).
-- Usage: psql -v readonly_password='<password>' -f 04_roles.sql
SELECT format(
    'CREATE ROLE bmp_readonly LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE',
    :'readonly_password'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'bmp_readonly'
)
\gexec

ALTER ROLE bmp_readonly WITH
    LOGIN
    PASSWORD :'readonly_password'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE;
ALTER ROLE bmp_readonly SET default_transaction_read_only = on;
ALTER ROLE bmp_readonly SET statement_timeout = '8s';
ALTER ROLE bmp_readonly SET lock_timeout = '2s';
ALTER ROLE bmp_readonly SET idle_in_transaction_session_timeout = '10s';
ALTER ROLE bmp_readonly SET search_path = public;
REVOKE ALL ON SCHEMA rag FROM bmp_readonly;
GRANT USAGE ON SCHEMA public TO bmp_readonly;
GRANT SELECT ON branches, product_categories, suppliers, products, promotions, calendar, monthly_sales_targets, sales_orders, sales_order_items, sales_returns, inventory_levels, inventory_snapshots, purchase_orders, purchase_order_items, stock_adjustments, v_sales_detail, v_inventory_status, v_weekly_product_demand TO bmp_readonly;
-- customers: column-level grant that omits email and phone
GRANT SELECT (customer_id, customer_code, customer_type, full_name, gender, age_group, city, region, customer_segment, loyalty_tier, loyalty_points, registration_date, acquisition_channel, preferred_branch_id, marketing_opt_in, contract_number, credit_limit, payment_terms_days, is_active) ON customers TO bmp_readonly;
