-- stg_orders.sql
-- Cleans and standardizes raw transaction data.
-- Calculates revenue after discount and flags bad shipping dates.

with source as (
    select * from {{ source('raw_stage', 'raw_transactions') }}
),

cleaned as (
    select
        -- identifiers
        order_id,
        user_id,
        product_id,

        -- dimensions
        lower(trim(category))        as category,
        lower(trim(status))          as status,
        lower(trim(payment_method))  as payment_method,
        upper(trim(country))         as country_code,
        trim(city)                   as city,

        -- measures
        cast(quantity as int64)                         as quantity,
        round(cast(unit_price as float64), 2)           as unit_price_usd,
        round(cast(discount_pct as float64), 4)         as discount_pct,

        -- calculated revenue: price * qty * (1 - discount)
        round(
            cast(unit_price as float64)
            * cast(quantity as int64)
            * (1 - cast(discount_pct as float64)),
        2) as revenue_usd,

        -- timestamps
        cast(order_date as timestamp)    as order_date,
        cast(shipping_date as timestamp) as shipping_date,

        -- data quality flag: shipping before order = bad data (injected in Day 1)
        case
            when cast(shipping_date as timestamp) < cast(order_date as timestamp)
            then true
            else false
        end as is_shipping_date_invalid

    from source
    where order_id is not null
      and user_id  is not null
)

select * from cleaned
