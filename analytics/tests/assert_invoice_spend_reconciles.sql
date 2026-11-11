-- No records should be returned on successful reconciliation.
with a as (select coalesce(sum(amount_eur),0) total from {{ ref('fct_invoices') }}),
     b as (select coalesce(sum(actual_eur),0) total from {{ ref('fct_budget_actuals') }})
select a.total as invoice_total,b.total as budget_actual_total from a cross join b
where abs(a.total-b.total)>0.01
