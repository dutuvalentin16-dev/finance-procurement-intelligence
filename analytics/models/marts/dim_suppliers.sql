select supplier_id,supplier_name,category,country from {{ ref('stg_suppliers') }}
