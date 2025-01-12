import uuid
import shutil
from datetime import datetime
from typing import Optional

import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.accounts.permissions import (
    hasAdminPermission,
    hasCreateProductPermission,
    hasWholeSalerPermission,
)
from app.accounts.services import get_current_user
from app.products.schemas import (
    ProductCreateSchema,
    ProductDetailSchema,
    ProductImageSchema,
    ProductCategory,
    ProductStatus,
)
from app.products.services import get_products_response
from app.core.auth import AuthHandler
from app.core._id import PyObjectId
from app.core.database import get_database
from app.core.helpers import transform_mongo_data
from app.core.pagination import paginate
from app.core import settings

ERROR_CODE = status.HTTP_404_NOT_FOUND
auth_handler = AuthHandler()
router = APIRouter(prefix="/products", tags=["Products"])

cloudinary.config(
    cloud_name=settings.CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
)


@router.get("/{id}")
async def get_single_product(
    id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    product = await db["products"].find_one({"_id": PyObjectId(id)})
    product = transform_mongo_data(product)
    return product


@router.get("")
async def get_products(
    category: Optional[ProductCategory] = None,
    status: Optional[ProductStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    product_status = (
        {"$in": ["available"]}
        if status == "available"
        else (
            {"$in": ["unavailable"]}
            if status == "unavailable"
            else {"$in": ["available", "unavailable", "out of stock"]}
        )
    )
    query = (
        {"status": product_status, "category": category}
        if category
        else {"status": product_status}
    )

    pipeline = [
        {"$match": query},
        {
            "$lookup": {
                "from": "product_images",
                "localField": "_id",
                "foreignField": "product_id",
                "as": "images",
            }
        },
    ]
    products_with_images = await db["products"].aggregate(pipeline).to_list(length=None)
    paginated_response = paginate(
        transform_mongo_data(products_with_images), page=page, page_size=page_size
    )
    return paginated_response


@router.post("", response_model=ProductDetailSchema)
async def create_product(
    product: ProductCreateSchema,
    current_user=Depends(auth_handler.auth_wrapper),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    product_in_db = await db["products"].find_one(
        {
            "name": product.name,
            "description": product.description,
            "seller_id": product.seller_id,
        }
    )
    if product_in_db:
        raise HTTPException(status_code=403, detail="Product already exists.")

    req_user = await get_current_user(current_user, db)
    if not hasCreateProductPermission(req_user):
        raise HTTPException(
            status_code=403,
            detail="Only wholesalers or admins can perform this action.",
        )

    new_product = await db["products"].insert_one(product.dict(by_alias=True))
    created_product = await db["products"].find_one({"_id": new_product.inserted_id})
    created_product = transform_mongo_data(created_product)
    return created_product


@router.patch("/{id}", response_model=ProductDetailSchema)
async def update_product(
    id: str,
    product: ProductCreateSchema,
    current_user=Depends(auth_handler.auth_wrapper),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    product_in_db = await db["products"].find_one({"_id": PyObjectId(id)})
    if not product_in_db:
        raise HTTPException(status_code=403, detail="Product not found.")

    req_user = await get_current_user(current_user, db)
    if not (
        hasAdminPermission(req_user) or req_user["_id"] == product_in_db["seller_id"]
    ):
        msg = "Only admins or product owner can perform this action."
        raise HTTPException(status_code=403, detail=msg)

    new_product = await db["products"].insert_one(product.dict(by_alias=True))
    created_product = await db["products"].find_one({"_id": new_product.inserted_id})
    created_product = transform_mongo_data(created_product)
    return created_product


@router.post("/{id}/images/", response_model=ProductImageSchema)
async def upload_product_image(
    id: str,
    file: UploadFile = File(...),
    current_user=Depends(auth_handler.auth_wrapper),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    product = await db["products"].find_one({"_id": PyObjectId(id)})
    req_user = await get_current_user(current_user, db)
    if not hasCreateProductPermission(req_user):
        raise HTTPException(status_code=400, detail="Not allowed, contact admin")

    if (
        hasWholeSalerPermission(req_user)
        and not req_user["_id"] == product["seller_id"]
    ):
        raise HTTPException(status_code=400, detail="Not allowed, contact admin")

    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(
            status_code=400, detail="Invalid file type. Only JPEG and PNG are allowed."
        )

    alt_text = f"{file.filename.split('.')[0]}.{file.filename.split('.')[-1]}"
    file_name = f"{uuid.uuid4()}"
    res = cloudinary.uploader.upload(file.file, public_id=file_name)
    image_url = res.get("url")

    image = await db["product_images"].insert_one(
        {
            "product_id": product["_id"],
            "url": image_url,
            "alt_text": alt_text,
            "created_at": datetime.now(),
        }
    )
    new_image = await db["product_images"].find_one({"_id": image.inserted_id})
    new_image = transform_mongo_data(new_image)

    await db["products"].find_one_and_update(
        {"_id": PyObjectId(id)},
        {"$push": {"images": new_image}},
        return_document=ReturnDocument.AFTER,
    )
    return new_image


@router.delete("/{id}/images")
async def delete_product_image(
    id: str,
    image_id: str,
    current_user=Depends(auth_handler.auth_wrapper),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    product = await db["products"].find_one({"_id": PyObjectId(id)})
    req_user = await get_current_user(current_user, db)
    if not hasCreateProductPermission(req_user):
        raise HTTPException(status_code=400, detail="Not allowed, contact admin")

    if (
        hasWholeSalerPermission(req_user)
        and not req_user["_id"] == product["seller_id"]
    ):
        raise HTTPException(status_code=400, detail="Not allowed, contact admin")

    db["product_images"].delete_one({"_id": PyObjectId(image_id)})
