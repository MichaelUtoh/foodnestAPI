import uuid
from datetime import datetime
from typing import List

import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.core.auth import AuthHandler
from app.core._id import PyObjectId
from app.core.database import get_database
from app.core.helpers import transform_mongo_data
from app.core.pagination import paginate
from app.accounts.permissions import hasAdminPermission
from app.accounts.schemas import (
    MFARequest,
    UserLoginResponseSchema,
    UserLoginSchema,
    UserRegisterSchema,
    UserUpdateSchema,
    UserUpdateRoleSchema,
    UserInfoResponseSchema,
    UserInfoPaginatedResponseSchema,
)
from app.accounts.services import (
    disable_user_mfa,
    get_current_user,
    generate_mfa_qrcode,
    verify_2fa_otp,
)

ERROR_CODE = status.HTTP_404_NOT_FOUND
auth_handler = AuthHandler()
router = APIRouter(
    prefix="/auth/users",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=UserLoginResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def login(
    user: UserLoginSchema, db: AsyncIOMotorDatabase = Depends(get_database)
):
    existing_user = await db["users"].find_one({"email": user.email})
    last_login_data = {"last_login": datetime.now()}
    await db["users"].update_one({"email": user.email}, {"$set": last_login_data})

    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User not found"
        )

    if not auth_handler.verify_password(user.password, existing_user["password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials"
        )

    return {
        "id": str(existing_user["_id"]),
        "email": existing_user["email"],
        "access_token": auth_handler.encode_token(user.email),
        "refresh_token": auth_handler.encode_refresh_token(user.email),
    }


@router.post(
    "/register",
    response_model=UserLoginResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    user: UserRegisterSchema, db: AsyncIOMotorDatabase = Depends(get_database)
):
    existing_user = await db["users"].find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    user_dict = user.model_dump()
    user_dict["password"] = auth_handler.get_password_hash(user.password)
    user_dict["created_at"] = user_dict["updated_at"] = datetime.now()
    res = await db["users"].insert_one(user_dict)
    new_user = await db["users"].find_one({"_id": res.inserted_id})

    return {
        "id": str(new_user["_id"]),
        "email": new_user["email"],
        "access_token": auth_handler.encode_token(new_user["email"]),
        "refresh_token": auth_handler.encode_refresh_token(new_user["email"]),
    }


@router.get("/{id}", response_model=UserInfoResponseSchema)
async def get_user(
    id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(auth_handler.auth_wrapper),
):
    user = await db["users"].find_one({"_id": PyObjectId(id)})
    req_user = await get_current_user(current_user, db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if (
        not req_user.get("role") == "admin"
        and not req_user.get("email") == user["email"]
    ):
        raise HTTPException(status_code=ERROR_CODE, detail="Not allowed, contact admin")

    user = transform_mongo_data(user)
    return user


@router.get(
    "",
    response_model=UserInfoPaginatedResponseSchema,
)
async def admin_get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(auth_handler.auth_wrapper),
):
    req_user = await get_current_user(current_user, db)
    if not hasAdminPermission(req_user):
        msg = "Only admins are allowed to perform this action."
        raise HTTPException(status_code=400, detail=msg)

    users = await db["users"].find().to_list(length=None)
    paginated_response = paginate(
        transform_mongo_data(users), page=page, page_size=page_size
    )
    return paginated_response


@router.patch("/{id}/role", response_model=UserInfoResponseSchema)
async def update_user_role(
    id: str,
    payload: UserUpdateRoleSchema,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(auth_handler.auth_wrapper),
):
    req_user = await get_current_user(current_user, db)
    user = await db["users"].find_one({"_id": PyObjectId(id)})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if not req_user.get("role") or not req_user.get("role") == "admin":
        raise HTTPException(status_code=ERROR_CODE, detail="Not allowed, contact admin")

    payload = payload.dict(exclude_unset=True)
    payload["updated_at"] = datetime.now()
    payload["last_updated_by"] = req_user.get("id")

    await db["users"].update_one({"_id": PyObjectId(id)}, {"$set": payload})
    updated_user = await db["users"].find_one({"_id": PyObjectId(id)})
    updated_user = transform_mongo_data(updated_user)
    return updated_user


@router.patch("/{id}", response_model=UserInfoResponseSchema)
async def update_user(
    id: str, payload: UserUpdateSchema, db: AsyncIOMotorDatabase = Depends(get_database)
):
    user = await db["users"].find_one({"_id": PyObjectId(id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    payload = payload.dict(exclude_unset=True)
    payload["updated_at"] = datetime.now()
    await db["users"].update_one({"_id": PyObjectId(id)}, {"$set": payload})
    updated_user = await db["users"].find_one({"_id": PyObjectId(id)})
    transform_mongo_data(update_user)
    return updated_user


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(auth_handler.auth_wrapper),
):
    req_user = await get_current_user(current_user, db)
    user = await db["users"].find_one({"_id": PyObjectId(id)})

    if not user:
        raise HTTPException(status_code=ERROR_CODE, detail="User not found")

    if not req_user.role == "admin":
        raise HTTPException(status_code=ERROR_CODE, detail="Not allowed, contact admin")

    await db["users"].delete_one({"_id": PyObjectId(id)})


@router.post("/{id}/images/")
async def upload_user_image(
    id: str,
    file: UploadFile = File(...),
    current_user=Depends(auth_handler.auth_wrapper),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user = await db["users"].find_one({"_id": PyObjectId(id)})
    req_user = await get_current_user(current_user, db)

    if not req_user["_id"] == user["_id"]:
        raise HTTPException(status_code=400, detail="Not allowed, contact admin")

    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(
            status_code=400, detail="Invalid file type. Only JPEG and PNG are allowed."
        )

    file_name = f"{uuid.uuid4()}"
    res = cloudinary.uploader.upload(file.file, public_id=file_name)
    image_url = res.get("url")

    await db["users"].find_one_and_update(
        {"_id": PyObjectId(id)},
        {"$set": {"image_url": image_url}},
        return_document=ReturnDocument.AFTER,
    )
    return {"detail": "Uploaded image successfully"}


@router.get("")
async def get_dashboard_data(
    current_user=Depends(auth_handler.auth_wrapper),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    data = {}
    return data


@router.post("/generate_mfa_secret")
async def generate_mfa_secret(
    current_user=Depends(auth_handler.auth_wrapper),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user = await db["users"].find_one({"email": current_user})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    qr_code, setup_key = await generate_mfa_qrcode(user, db)
    return {"qr_code": qr_code, "setup_key": setup_key}


@router.post("/disable_mfa")
async def disable_mfa(
    current_user=Depends(auth_handler.auth_wrapper),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user = await db["users"].find_one({"email": current_user})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await disable_user_mfa
    return {"detail": "MFA has been disabled for this user."}


@router.post("/configure_mfa")
async def configure_mfa(
    data: MFARequest,
    current_user=Depends(auth_handler.auth_wrapper),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user = await db["users"].find_one({"email": current_user})
    print("••• ", user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    verified = await verify_2fa_otp(user, data.otp_code, db)
    if not verified:
        raise HTTPException(status_code=404, detail="User not found")

    return {"detail": "MFA configured successfully"}
