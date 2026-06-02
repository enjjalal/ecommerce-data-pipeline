-- mart_finance_performance.sql
-- Final business-level table joining orders + user profiles.
-- Computes running cumulative revenue and user lifetime value
-- using window functions.

with orders as (
    select * from {{ ref('stg_orders') }}
),

users as (
    select * from {{ ref('stg_users') }}
),

-- Only include completed orders for financial reporting
completed_orders as (
    select * from orders
    where status = 'completed'
      and is_shipping_date_invalid = false
),

-- Join orders to user engagement profiles
enriched as (
    select
        -- order fields
        o.order_id,
        o.user_id,
        o.product_id,
        o.category,
        o.payment_method,
        o.country_code,
        o.city,
        o.quantity,
        o.unit_price_usd,
        o.discount_pct,
        o.revenue_usd,
        o.order_date,
        o.shipping_date,

        -- user engagement fields
        u.total_sessions,
        u.total_clicks,
        u.avg_time_on_page_sec,
        u.total_cta_clicks,
        u.primary_device,
        u.primary_referrer,
        u.first_seen_at,
        u.last_seen_at

    from completed_orders o
    left join users u
        on o.user_id = u.user_id
),

-- Apply window functions for financial analytics
with_window_metrics as (
    select
        *,

        -- 1. Running cumulative revenue ordered by time
        -- Shows total revenue accumulated up to and including this order
        sum(revenue_usd) over (
            order by order_date
            rows between unbounded preceding and current row
        ) as cumulative_revenue_usd,

        -- 2. User lifetime value: total revenue this user has generated
        sum(revenue_usd) over (
            partition by user_id
        ) as user_lifetime_value_usd,

        -- 3. User order rank: which order number is this for the user
        row_number() over (
            partition by user_id
            order by order_date
        ) as user_order_sequence,

        -- 4. Revenue contribution: this order's % of total revenue
        round(
            revenue_usd / nullif(sum(revenue_usd) over (), 0) * 100,
        4) as revenue_share_pct,

        -- 5. 7-day rolling revenue window (604800 = 7 * 24 * 60 * 60 seconds)
        sum(revenue_usd) over (
            order by unix_seconds(order_date)
            range between 604800 preceding and current row
        ) as rolling_7d_revenue_usd

    from enriched
)

select * from with_window_metrics
