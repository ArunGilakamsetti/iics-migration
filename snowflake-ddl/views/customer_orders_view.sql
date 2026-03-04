CREATE OR REPLACE VIEW sales_schema.customer_orders_view AS
SELECT 
    c.customer_id,
    c.first_name || ' ' || c.last_name AS customer_name,
    o.order_id,
    o.order_date,
    p.product_name,
    o.quantity,
    o.total_amount
FROM sales_schema.orders o
JOIN sales_schema.customers c ON o.customer_id = c.customer_id
JOIN sales_schema.products p ON o.product_id = p.product_id;
