from __future__ import annotations

import datetime
import random
from pathlib import Path

import polars as pl


REGIONS = ["East", "West", "North", "South", "Central"]
PRODUCT_CATEGORIES = ["Electronics", "Clothing", "Food", "Home", "Sports"]
PRODUCTS = {
    "Electronics": ["Phone", "Laptop", "Tablet", "Headphones", "Camera"],
    "Clothing": ["Shirt", "Pants", "Dress", "Shoes", "Jacket"],
    "Food": ["Snacks", "Beverages", "Dairy", "Meat", "Bakery"],
    "Home": ["Furniture", "Appliances", "Decor", "Bedding", "Kitchen"],
    "Sports": ["Ball", "Shoes", "Clothes", "Equipment", "Accessories"],
}
CUSTOMER_TYPES = ["VIP", "Regular", "New", "Wholesale"]
CHANNELS = ["Online", "Offline", "Mobile", "Social"]


def generate_sales_data(
    num_rows: int = 10000,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    seed: int = 42,
) -> pl.DataFrame:
    random.seed(seed)

    if start_date is None:
        start_date = datetime.date(2024, 1, 1)
    if end_date is None:
        end_date = datetime.date(2024, 12, 31)

    date_range = (end_date - start_date).days

    dates = []
    regions = []
    product_categories = []
    products = []
    customer_types = []
    channels = []
    sales_amounts = []
    order_ids = []
    customer_ids = []
    quantities = []
    last_modified = []

    for i in range(num_rows):
        random_days = random.randint(0, date_range)
        order_date = start_date + datetime.timedelta(days=random_days)
        dates.append(order_date)

        region = random.choice(REGIONS)
        regions.append(region)

        category = random.choice(PRODUCT_CATEGORIES)
        product_categories.append(category)
        product = random.choice(PRODUCTS[category])
        products.append(product)

        customer_type = random.choice(CUSTOMER_TYPES)
        customer_types.append(customer_type)

        channel = random.choice(CHANNELS)
        channels.append(channel)

        quantity = random.randint(1, 20)
        quantities.append(quantity)

        base_price = {
            "Electronics": 500,
            "Clothing": 50,
            "Food": 10,
            "Home": 200,
            "Sports": 80,
        }[category]

        amount = round(base_price * quantity * random.uniform(0.7, 1.3), 2)
        sales_amounts.append(amount)

        order_ids.append(f"ORD{i+1:08d}")
        customer_ids.append(f"CUST{random.randint(1, 2000):06d}")

        last_modified.append(
            order_date + datetime.timedelta(days=random.randint(0, 30))
        )

    df = pl.DataFrame(
        {
            "order_date": dates,
            "region": regions,
            "product_category": product_categories,
            "product": products,
            "customer_type": customer_types,
            "channel": channels,
            "quantity": quantities,
            "sales_amount": sales_amounts,
            "order_id": order_ids,
            "customer_id": customer_ids,
            "last_modified": last_modified,
        }
    )

    return df


def get_dimension_schemas() -> list[dict]:
    return [
        {
            "name": "order_date",
            "type": "time",
            "description": "Order date",
            "column": "order_date",
            "hierarchies": ["year", "quarter", "month", "day"],
        },
        {
            "name": "region",
            "type": "geo",
            "description": "Sales region",
            "column": "region",
        },
        {
            "name": "product_category",
            "type": "product",
            "description": "Product category",
            "column": "product_category",
        },
        {
            "name": "product",
            "type": "product",
            "description": "Product name",
            "column": "product",
        },
        {
            "name": "customer_type",
            "type": "customer",
            "description": "Customer type",
            "column": "customer_type",
        },
        {
            "name": "channel",
            "type": "channel",
            "description": "Sales channel",
            "column": "channel",
        },
    ]


def get_measure_schemas() -> list[dict]:
    return [
        {
            "name": "sales_amount",
            "type": "sum",
            "description": "Total sales amount",
            "column": "sales_amount",
            "agg": "sum",
        },
        {
            "name": "order_count",
            "type": "count",
            "description": "Number of orders",
            "column": "order_id",
            "agg": "count",
        },
        {
            "name": "avg_order_value",
            "type": "avg",
            "description": "Average order value",
            "column": "sales_amount",
            "agg": "avg",
        },
        {
            "name": "customer_count",
            "type": "distinct_count",
            "description": "Number of unique customers",
            "column": "customer_id",
            "agg": "distinct_count",
        },
        {
            "name": "quantity_sum",
            "type": "sum",
            "description": "Total quantity sold",
            "column": "quantity",
            "agg": "sum",
        },
    ]


def setup_sample_cube(
    cube_name: str = "sales",
    num_rows: int = 10000,
    data_dir: str = "./data",
) -> None:
    from app.config import settings
    from app.models import DimensionSchema, MeasureSchema
    from app.storage.parquet_store import ParquetStore
    from app.storage.metadata_db import init_db
    from app.storage.metadata_store import metadata_store

    init_db()

    store = ParquetStore(base_dir=data_dir + "/parquet")
    df = generate_sales_data(num_rows=num_rows)
    store.overwrite(cube_name, df)

    dimensions = [DimensionSchema(**d) for d in get_dimension_schemas()]
    measures = [MeasureSchema(**m) for m in get_measure_schemas()]

    existing = metadata_store.get_cube(cube_name)
    if existing:
        metadata_store.delete_cube(cube_name)

    metadata_store.create_cube(
        name=cube_name,
        fact_table=cube_name,
        dimensions=dimensions,
        measures=measures,
        description="Sample sales cube with mock data",
    )
    metadata_store.update_cube_stats(cube_name, num_rows)
    print(f"Sample cube '{cube_name}' created with {num_rows} rows")


if __name__ == "__main__":
    setup_sample_cube()
