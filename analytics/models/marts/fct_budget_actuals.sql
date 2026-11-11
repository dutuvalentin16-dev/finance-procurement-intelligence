-- Grain: brand x month x category. Aggregate invoices BEFORE joining budgets.
with spend as (
 select brand_id, strftime(invoice_date,'%Y-%m') as spend_month,category,
        sum(amount_eur) as actual_eur,count(*) as invoice_count
 from {{ ref('fct_invoices') }} group by 1,2,3
)
select b.brand_id,b.budget_month,b.category,b.budget_eur,
       coalesce(s.actual_eur,0) as actual_eur,
       b.budget_eur-coalesce(s.actual_eur,0) as remaining_eur,
       coalesce(s.invoice_count,0) as invoice_count
from {{ ref('stg_budgets') }} b
left join spend s on s.brand_id=b.brand_id and s.spend_month=b.budget_month and s.category=b.category
