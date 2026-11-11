select cast(invoice_id as varchar) as invoice_id,
       cast(supplier_id as varchar) as supplier_id,
       cast(brand_id as varchar) as brand_id,
       nullif(cast(po_id as varchar), '') as po_id,
       cast(currency as varchar) as currency,
       cast(amount as decimal(18,2)) as invoice_amount,
       try_cast(invoice_date as date) as invoice_date,
       cast(status as varchar) as status,
       cast(source as varchar) as source
from {{ ref('invoices') }}
