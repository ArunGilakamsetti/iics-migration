CREATE OR REPLACE TABLE sales_schema.customers (
    customer_id INT AUTOINCREMENT PRIMARY KEY,
    first_name STRING,
    last_name STRING,
    email STRING,
    phone STRING,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
