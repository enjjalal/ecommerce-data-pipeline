-- stg_users.sql
-- Derives a clean user dimension from the clickstream data.
-- Each row = one unique user with their behavioural summary.

with source as (
    select * from {{ source('raw_stage', 'raw_user_clicks') }}
),

cleaned as (
    select
        click_id,
        user_id,
        session_id,

        lower(trim(page))     as page,
        lower(trim(device))   as device,
        lower(trim(referrer)) as referrer,

        cast(time_on_page_sec as int64) as time_on_page_sec,
        cast(clicked_cta as bool)       as clicked_cta,
        cast(timestamp as timestamp)    as event_timestamp

    from source
    where click_id is not null
      and user_id  is not null
),

-- Aggregate to one row per user — their overall engagement profile
user_summary as (
    select
        user_id,
        count(distinct session_id)              as total_sessions,
        count(click_id)                         as total_clicks,
        round(avg(time_on_page_sec), 1)         as avg_time_on_page_sec,
        countif(clicked_cta = true)             as total_cta_clicks,
        min(event_timestamp)                    as first_seen_at,
        max(event_timestamp)                    as last_seen_at,
        -- most frequent device
        approx_top_count(device, 1)[offset(0)].value    as primary_device,
        -- most frequent referrer
        approx_top_count(referrer, 1)[offset(0)].value  as primary_referrer
    from cleaned
    group by user_id
)

select * from user_summary
