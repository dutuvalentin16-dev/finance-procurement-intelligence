"""Run on a Databricks notebook with Spark, or a local PySpark installation.
Synthetic-only batch rebuild; no cloud credentials, external reads or persistent writes.
"""
from pyspark.sql import SparkSession, functions as F, Window


def run(spark):
    events = spark.createDataFrame([
        ('A001','North','2025-03-01'), ('A002','West','2025-03-01'),
        ('A001','South','2025-04-01'),
    ], ['account_id','region','effective_date']).withColumn('effective_date', F.to_date('effective_date'))
    sales = spark.createDataFrame([
        ('S001','A001','2025-03-01',100000,'R001'), ('S002','A002','2025-03-01',250000,'R002'),
        ('S003','A001','2025-04-01',300000,'R001'), ('S004','A002','2025-04-01',150000,'R002'),
        ('S005','A001','2025-03-15',50000,'R001'),
    ], ['sale_id','account_id','booked_on','amount_cents','rep']).withColumn('booked_on', F.to_date('booked_on'))
    w = Window.partitionBy('account_id').orderBy('effective_date')
    changes = events.withColumn('previous_region', F.lag('region').over(w)).where(F.col('previous_region').isNull() | (F.col('region') != F.col('previous_region')))
    dim = changes.withColumn('valid_to', F.lead('effective_date').over(w)).drop('previous_region')
    sales.createOrReplaceTempView('demo_sales')
    dim.createOrReplaceTempView('demo_account_history')
    detail = spark.sql('''SELECT s.*, d.region FROM demo_sales s JOIN demo_account_history d
        ON s.account_id=d.account_id AND s.booked_on>=d.effective_date
        AND (d.valid_to IS NULL OR s.booked_on<d.valid_to)''')
    detail.createOrReplaceTempView('demo_sales_detail')
    qbr = spark.sql('''SELECT concat(year(booked_on), '-Q', quarter(booked_on)) AS period,
        region, count(*) AS bookings, sum(amount_cents) AS booked_cents
        FROM demo_sales_detail GROUP BY 1, 2 ORDER BY 1, 2''')
    compensation = spark.sql('''SELECT concat(year(booked_on), '-Q', quarter(booked_on)) AS period,
        rep, sum(amount_cents) AS booked_cents, sum((amount_cents*5+50) DIV 100) AS commission_cents
        FROM demo_sales_detail GROUP BY 1, 2 ORDER BY 1, 2''')
    assert detail.count() == sales.count() == 5
    assert qbr.agg(F.sum('booked_cents')).first()[0] == 850000
    assert compensation.agg(F.sum('commission_cents')).first()[0] == 42500
    assert detail.where("sale_id='S005'").first()['region'] == 'North'
    qbr.show(); compensation.show()


if __name__ == '__main__':
    run(SparkSession.builder.appName('SyntheticSalesReference').getOrCreate())
