-- Grain: one synthetic source invoice. Values are converted to EUR at fixed illustrative rates.
with base as (
 select i.invoice_id,i.supplier_id,i.brand_id,i.po_id,i.currency,
        i.invoice_amount,i.invoice_date,i.status,i.source,
        s.category,b.brand_name,s.supplier_name,
        round(i.invoice_amount * f.eur_rate,2) as amount_eur,
        p.po_amount,p.supplier_id as po_supplier_id,p.brand_id as po_brand_id,
        row_number() over (partition by i.supplier_id,i.po_id,i.invoice_amount,i.invoice_date
                           order by i.invoice_id) as business_event_sequence
 from {{ ref('stg_invoices') }} i
 join {{ ref('dim_suppliers') }} s on s.supplier_id=i.supplier_id
 join {{ ref('dim_brands') }} b on b.brand_id=i.brand_id
 join {{ ref('stg_fx_rates') }} f on f.currency=i.currency
 left join {{ ref('stg_purchase_orders') }} p on p.po_id=i.po_id
)
select invoice_id,supplier_id,brand_id,po_id,currency,invoice_amount,amount_eur,
       invoice_date,status,source,category,brand_name,supplier_name,
       case when po_id is not null and business_event_sequence > 1 then 'DUPLICATE'
            when po_id is null or po_amount is null then 'MISSING_PO'
            when po_supplier_id <> supplier_id or po_brand_id <> brand_id then 'PO_MISMATCH'
            when invoice_amount > po_amount * 1.10 then 'OVER_PO_LIMIT'
            else 'PASS' end as control_status
from base
