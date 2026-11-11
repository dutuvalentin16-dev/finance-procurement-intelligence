-- Fixed demonstrative FX rates. They are NOT market/live exchange rates.
select 'EUR' as currency, cast(1.00 as decimal(8,4)) as eur_rate
union all select 'USD', cast(0.91 as decimal(8,4))
union all select 'GBP', cast(1.17 as decimal(8,4))
union all select 'RON', cast(0.20 as decimal(8,4))
