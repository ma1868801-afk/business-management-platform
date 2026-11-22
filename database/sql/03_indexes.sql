-- Recommended indexes (docs/03_database_design.md section 6). Created after the data load for speed.
CREATE UNIQUE INDEX ux_branches_code ON branches (branch_code);
CREATE UNIQUE INDEX ux_products_sku ON products (sku);
CREATE UNIQUE INDEX ux_customers_code ON customers (customer_code);
CREATE UNIQUE INDEX ux_sales_orders_number ON sales_orders (order_number);
CREATE INDEX ix_sales_orders_date ON sales_orders (order_date);
CREATE INDEX ix_sales_orders_branch_date ON sales_orders (branch_id, order_date);
CREATE INDEX ix_sales_orders_customer ON sales_orders (customer_id);
CREATE INDEX ix_sales_orders_status_date ON sales_orders (status, order_date);
CREATE INDEX ix_sales_items_order ON sales_order_items (order_id);
CREATE INDEX ix_sales_items_product ON sales_order_items (product_id);
CREATE INDEX ix_sales_returns_item ON sales_returns (order_item_id);
CREATE INDEX ix_sales_returns_date ON sales_returns (return_date);
CREATE UNIQUE INDEX ux_inventory_levels_loc ON inventory_levels (branch_id, product_id);
CREATE INDEX ix_inventory_snapshots_series ON inventory_snapshots (product_id, branch_id, snapshot_date);
CREATE INDEX ix_purchase_orders_supplier ON purchase_orders (supplier_id, order_date);
CREATE INDEX ix_purchase_items_po ON purchase_order_items (po_id);
CREATE INDEX ix_stock_adjustments_series ON stock_adjustments (product_id, branch_id, adjustment_date);
ANALYZE;
