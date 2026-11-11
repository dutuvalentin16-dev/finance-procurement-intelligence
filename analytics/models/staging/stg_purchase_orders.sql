select cast(po_id as varchar) as po_id,
       cast(supplier_id as varchar) as supplier_id,
       cast(brand_id as varchar) as brand_id,
       cast(currency as varchar) as currency,
       cast(po_amount as decimal(18,2)) as po_amount,
       try_cast(created_at as date) as created_at
from {{ ref('purchase_orders') }}
