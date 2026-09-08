from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from app.core.errors import ErrorCode
from app.core.responses import ApiResponse, ErrorInfo
from app.schemas import AddressChangeRequest, TicketResponse
from app.services.ticket_service import create_address_change_ticket
from app.schemas import (
    ComplaintRequest,
    HumanRequest,
    TicketCreateApiRequest,
    TicketResponse,
)
from app.services.ticket_service import (
    create_address_change_ticket,
    create_complaint_ticket,
    create_human_ticket,
    get_ticket,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["工单"],
)


@router.post(
    "/orders/{order_id}/address-change-requests",
    response_model=ApiResponse,
)
def create_address_change_request(
    order_id: str,
    request: AddressChangeRequest,
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

    service_request = AddressChangeRequest(
        order_id=order_id,
        new_address=request.new_address,
        confirmed=request.confirmed,
        client_request_id=request.client_request_id,
    )

    try:
        ticket = create_address_change_ticket(
            service_request,
            user_id=x_user_id,
        )

    except ValueError as error:
        message = str(error)

        if "尚未确认" in message:
            code = ErrorCode.MISSING_REQUIRED_FIELD
            status_code = 400
        elif "不允许改址" in message:
            code = ErrorCode.ORDER_ALREADY_DELIVERED
            status_code = 409
        elif "订单不存在或无权访问" in message:
            code = ErrorCode.ORDER_NOT_FOUND
            status_code = 404
        else:
            code = ErrorCode.MISSING_REQUIRED_FIELD
            status_code = 400

        response = ApiResponse(
            success=False,
            data=None,
            error=ErrorInfo(
                code=code,
                message=message,
            ),
        )

        return JSONResponse(
            status_code=status_code,
            content=response.model_dump(),
        )

    response_data = TicketResponse(
        **ticket,
    )

    return ApiResponse(
        success=True,
        data=response_data.model_dump(),
        error=None,
    )

@router.post(
    "/tickets",
    response_model=ApiResponse,
)
def create_ticket_request(
    request: TicketCreateApiRequest,
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
        if request.type == "complaint":
            if not request.description:
                raise ValueError("投诉内容不能为空")

            if not request.contact:
                raise ValueError("投诉联系方式不能为空")

            service_request = ComplaintRequest(
                order_id=request.order_id,
                description=request.description,
                contact=request.contact,
                client_request_id=request.client_request_id,
            )

            ticket = create_complaint_ticket(
                service_request,
                user_id=x_user_id,
            )

        else:
            if not request.content:
                raise ValueError("人工工单内容不能为空")

            service_request = HumanRequest(
                content=request.content,
                contact=request.contact,
                client_request_id=request.client_request_id,
            )

            ticket = create_human_ticket(
                service_request,
                user_id=x_user_id,
            )

    except ValueError as error:
        message = str(error)

        if "订单不存在或无权访问" in message:
            code = ErrorCode.ORDER_NOT_FOUND
            status_code = 404
        else:
            code = ErrorCode.MISSING_REQUIRED_FIELD
            status_code = 400

        response = ApiResponse(
            success=False,
            data=None,
            error=ErrorInfo(
                code=code,
                message=message,
            ),
        )

        return JSONResponse(
            status_code=status_code,
            content=response.model_dump(),
        )

    response_data = TicketResponse(**ticket)

    return ApiResponse(
        success=True,
        data=response_data.model_dump(),
        error=None,
    )
@router.get(
    "/tickets/{ticket_no}",
    response_model=ApiResponse,
)
def query_ticket(
    ticket_no: str,
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
        ticket = get_ticket(
            ticket_no,
            user_id=x_user_id,
        )

    except ValueError as error:
        message = str(error)

        if message == "工单不存在":
            code = ErrorCode.TICKET_NOT_FOUND
            status_code = 404
            public_message = "工单不存在或无权访问"
        else:
            code = ErrorCode.TICKET_NOT_FOUND
            status_code = 404
            public_message = "工单不存在或无权访问"

        response = ApiResponse(
            success=False,
            data=None,
            error=ErrorInfo(
                code=code,
                message=public_message,
            ),
        )

        return JSONResponse(
            status_code=status_code,
            content=response.model_dump(),
        )

    response_data = TicketResponse(**ticket)

    return ApiResponse(
        success=True,
        data=response_data.model_dump(),
        error=None,
    )