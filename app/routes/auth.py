"""Development-only consumer authentication endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel, Field


DEMO_PHONE = "13800000001"
DEMO_CODE = "123456"
DEMO_USER = {
    "user_id": "demo-user-001",
    "name": "张三",
    "phone_masked": "138****0001",
}


class PhoneRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=20)


class LoginRequest(PhoneRequest):
    code: str = Field(min_length=6, max_length=6)


router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


@router.post("/send-code")
def send_code(request: PhoneRequest):
    if request.phone != DEMO_PHONE:
        return {
            "success": False,
            "data": None,
            "error": {"code": "PHONE_NOT_FOUND", "message": "演示账号不存在"},
        }

    return {
        "success": True,
        "data": {
            "phone_masked": DEMO_USER["phone_masked"],
            "expires_in": 300,
            "dev_code": DEMO_CODE,
        },
        "error": None,
    }


@router.post("/login")
def login(request: LoginRequest):
    if request.phone != DEMO_PHONE or request.code != DEMO_CODE:
        return {
            "success": False,
            "data": None,
            "error": {"code": "INVALID_CODE", "message": "手机号或验证码错误"},
        }

    return {
        "success": True,
        "data": DEMO_USER,
        "error": None,
    }
