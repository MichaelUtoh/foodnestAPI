from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId

from app.core._id import PyObjectId


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderItem(BaseModel):
    product_id: str
    quantity: int


class OrderItemDetail(BaseModel):
    order_id: str
    product_id: str
    product_description: str
    product_name: str
    price: float
    quantity: int
    subtotal: float


class OrderDetailSchema(BaseModel):
    id: Optional[str] = Field(default_factory=PyObjectId, alias="_id")
    buyer_id: str = Field(..., description="The Retailer who placed the order")
    items: List[OrderItemDetail]
    total_price: float
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class OrderCreateSchema(BaseModel):
    items: List[OrderItem]


class OrderUpdateSchema(BaseModel):
    id: str
    items: List[OrderItem]
