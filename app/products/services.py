def get_products_response(products: list):
    return [
        {
            "id": str(i.get("_id")),
            "name": i.get("name"),
            "description": i.get("description"),
            "category": i.get("category"),
            "price_per_unit": i.get("price_per_unit"),
            "stock_quantity": i.get("stock_quantity"),
            "unit": i.get("unit"),
            "seller_id": i.get("seller_id"),
            "is_available": i.get("is_available"),
            "created_at": i.get("created_at"),
        }
        for i in products
    ]
