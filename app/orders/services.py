from datetime import datetime

from fastapi import HTTPException

from app.core._id import PyObjectId
from app.orders.schemas import OrderStatus


async def initiate_order(req_user, payload, db):
    order_data = {
        "buyer_id": req_user["_id"],
        "items": [],
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "status": OrderStatus.PENDING,
        "total_price": 0.0,
    }
    order = await db["orders"].insert_one(order_data)
    return order


async def build_order_item_list(order_id, order_item_list, order_items, db):
    for item in order_items:
        product = await db["products"].find_one({"_id": PyObjectId(item["product_id"])})
        item_info = {
            "order_id": str(order_id),
            "product_id": item["product_id"],
            "product_name": product["name"],
            "product_description": product["description"],
            "price": float(product["price_per_unit"]),
            "quantity": item["quantity"],
            "subtotal": float(product["price_per_unit"]) * item["quantity"],
        }
        order_item_list.append(item_info)
    return order_item_list


async def order_create_job(req_user, payload: dict, db) -> list:
    try:
        order_items = payload.dict()["items"]
        order_item_list = []
        order = await initiate_order(req_user, payload, db)
        order_id = order.inserted_id
        order_item_list = await build_order_item_list(
            order_id, order_item_list, order_items, db
        )

        await db["orders"].update_one(
            {"_id": PyObjectId(order.inserted_id)},
            {
                "$push": {"items": {"$each": [item for item in order_item_list]}},
                "$set": {
                    "updated_at": datetime.now(),
                    "total_price": sum([item["subtotal"] for item in order_item_list]),
                },
            },
        )
        return order_item_list
    except Exception as e:
        raise HTTPException(f"Something went wrong: {e}")


async def order_update_job(order, order_list, order_items, db):
    order_item_list = await build_order_item_list(
        order["id"], order_list, order_items, db
    )
    return order_item_list
