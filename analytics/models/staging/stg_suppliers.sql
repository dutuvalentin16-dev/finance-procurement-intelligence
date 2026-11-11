select cast(supplier_id as varchar) as supplier_id,
       cast(supplier_name as varchar) as supplier_name,
       cast(category as varchar) as category,
       cast(country as varchar) as country
from {{ ref('suppliers') }}
