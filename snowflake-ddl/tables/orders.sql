CREATE OR REPLACE TABLE sales_schema.orders (
    order_id INT AUTOINCREMENT PRIMARY KEY,
    customer_id INT,
    product_id INT,
    order_date DATE,
    quantity INT,
    total_amount NUMBER(10,2),
    FOREIGN KEY (customer_id) REFERENCES sales_schema.customers(customer_id),
    FOREIGN KEY (product_id) REFERENCES sales_schema.products(product_id)
);
