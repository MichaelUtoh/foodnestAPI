import base64
import io
import pyotp
import qrcode
from fastapi import Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core._id import PyObjectId
from app.core.database import get_database


async def get_current_user(email, db):
    return await db["users"].find_one({"email": email})


async def verify_2fa_otp(user, otp, db):
    totp = pyotp.TOTP(user["mfa_secret"])
    if totp.verify(otp):
        await db["users"].update_one(
            {"_id": PyObjectId(user["_id"])}, {"$set": {"mfa_enabled": True}}
        )
        return True
    return False


async def generate_mfa_qrcode(user, db):
    if (
        "mfa_secret" not in user
        or "mfa_enabled" not in user
        or not user["mfa_secret"]
        or not user["mfa_enabled"]
    ):
        new_mfa_secret = pyotp.random_base32()
        await db["users"].update_one(
            {"_id": PyObjectId(user["_id"])},
            {"$set": {"mfa_secret": new_mfa_secret, "mfa_enabled": True}},
        )
        user["mfa_secret"] = new_mfa_secret

    otp_uri = pyotp.TOTP(user["mfa_secret"]).provisioning_uri(
        name=user["email"], issuer_name="Foodnest Application"
    )

    qr = qrcode.make(otp_uri)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")

    buffer.seek(0)
    qr_code_data_uri = (
        f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
    )

    return qr_code_data_uri, user["mfa_secret"]


async def disable_user_mfa(user, db):
    if (
        "mfa_secret" not in user
        or "mfa_enabled" not in user
        or not user["mfa_secret"]
        or not user["mfa_enabled"]
    ):
        msg = "MFA is not enabled for this user."
        raise HTTPException(status_code=404, detail=msg)

    await db["users"].update_one(
        {"_id": PyObjectId(user["_id"])},
        {"$set": {"mfa_secret": "", "mfa_enabled": False}},
    )

    return True
