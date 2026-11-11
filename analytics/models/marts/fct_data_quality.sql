select control_status,count(*) as invoice_count,
       sum(amount_eur) as affected_spend_eur
from {{ ref('fct_invoices') }}
group by 1
