select cast(brand_id as varchar) as brand_id,
       cast(month as varchar) as budget_month,
       cast(category as varchar) as category,
       cast(budget_eur as decimal(18,2)) as budget_eur
from {{ ref('budgets') }}
