-- assert_shipping_date_after_order_date.sql
-- Custom singular test: catches orders where shipping happened before the order was placed.
-- This is a logical impossibility and indicates either bad source data or a pipeline bug.
-- dbt expects this query to return 0 rows. Any rows returned = test failure.

select
    order_id,
    user_id,
    order_date,
    shipping_date,
    timestamp_diff(shipping_date, order_date, hour) as hours_diff
from {{ ref('stg_orders') }}
where shipping_date < order_date
