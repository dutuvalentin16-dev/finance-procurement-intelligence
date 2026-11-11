select supplier_id,supplier_name,category,
       count(*) as invoice_count,
       sum(amount_eur) as total_spend_eur,
       sum(case when control_status <> 'PASS' then 1 else 0 end) as alert_count
from {{ ref('fct_invoices') }}
group by 1,2,3
