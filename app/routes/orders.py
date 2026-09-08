from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from app.core.errors import ErrorCode, OrderAccessDeniedError
from app.core.responses import ApiResponse, ErrorInfo
from app.schemas import OrderTrackingResponse
from app.services.order_service import get_order_tracking


router = APIRouter(
    prefix="/api/orders",
    tags=["订单"],
)

v1_router = APIRouter(
    prefix="/api/v1/orders",
    tags=["订单 V1"],
)


@v1_router.get("/{order_id}/tracking")
def query_order_tracking_v1(
    order_id: str,
    x_user_id: str | None = Header(
        default=None,
        alias="X-User-Id",
    ),
):
    if not x_user_id:
        response = ApiResponse(
            success=False,
            data=None,
            error=ErrorInfo(
                code=ErrorCode.MISSING_REQUIRED_FIELD,
                message="缺少用户身份信息",
            ),
        )

        return JSONResponse(
            status_code=400,
            content=response.model_dump(),
        )

    try:
        result = get_order_tracking(
            order_id.upper(),
            user_id=x_user_id,
        )
    except OrderAccessDeniedError:
        response = ApiResponse(
            success=False,
            data=None,
            error=ErrorInfo(
                code=ErrorCode.ORDER_ACCESS_DENIED,
                message="订单不存在或无权访问",
            ),
        )

        return JSONResponse(
            status_code=403,
            content=response.model_dump(),
        )

    if result is None:
        response = ApiResponse(
            success=False,
            data=None,
            error=ErrorInfo(
                code=ErrorCode.ORDER_NOT_FOUND,
                message="订单不存在或无权访问",
            ),
        )

        return JSONResponse(
            status_code=404,
            content=response.model_dump(),
        )

    return ApiResponse(
        success=True,
        data=result,
        error=None,
    )


@router.get(
    "/{order_no}/tracking",
    response_model=OrderTrackingResponse,
)
def query_order_tracking(order_no: str):
    """根据订单号查询物流轨迹。"""
    result = get_order_tracking(order_no.upper())

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"没有找到订单：{order_no}",
        )

    return result