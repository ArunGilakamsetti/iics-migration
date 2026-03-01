CREATE OR REPLACE TABLE sales_schema.products (
    product_id INT AUTOINCREMENT PRIMARY KEY,
    product_name STRING,
    category STRING,
    price NUMBER(10,2),
    stock_quantity INT
);
