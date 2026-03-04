CREATE OR REPLACE PROCEDURE sales_schema.calculate_loyalty_points(customer_id INT)
RETURNS INT
LANGUAGE SQL
AS
$$
    DECLARE points INT;
    BEGIN
        SELECT SUM(total_amount/10) INTO points
        FROM sales_schema.orders
        WHERE customer_id = :customer_id;

        RETURN COALESCE(points, 0);
    END;
$$;
