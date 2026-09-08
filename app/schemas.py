from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class TrackingEvent(BaseModel):
    event_time: str
    location: str
    description: str


class OrderTrackingResponse(BaseModel):
    order_no: str
    customer_name: str
    carrier: str
    tracking_no: str
    status: str
    tracking_events: list[TrackingEvent]
TicketType = Literal[
    "address_change",
    "complaint",
    "human",
]

TicketStatus = Literal[
    "pending",
    "processing",
    "completed",
    "rejected",
    "cancelled",
]


class TicketCreateRequest(BaseModel):
    """创建工单的请求模型。"""

    order_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    type: TicketType
    content: str = Field(
        min_length=1,
        max_length=2000,
    )
    client_request_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )


class TicketResponse(BaseModel):
    """工单对外响应模型。"""

    ticket_no: str
    user_id: str
    order_id: str | None
    type: TicketType
    content: str
    status: TicketStatus
    client_request_id: str | None
    created_at: str

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_created_at(cls, value: Any) -> str:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value)

class AddressChangeRequest(BaseModel):
    """改址申请请求模型。"""

    order_id: str = Field(
        min_length=1,
        max_length=50,
    )
    new_address: str = Field(
        min_length=5,
        max_length=200,
    )
    confirmed: bool = False
    client_request_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
class ComplaintRequest(BaseModel):
    """投诉工单请求模型。"""

    order_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    description: str = Field(
        min_length=1,
        max_length=2000,
    )
    contact: str = Field(
        min_length=3,
        max_length=100,
    )
    client_request_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )


class HumanRequest(BaseModel):
    """人工工单请求模型。"""

    content: str = Field(
        min_length=1,
        max_length=2000,
    )
    contact: str | None = Field(
        default=None,
        min_length=3,
        max_length=100,
    )
    client_request_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

class TicketCreateApiRequest(BaseModel):
    """投诉和人工工单的统一 HTTP 请求模型。"""

    type: Literal["complaint", "human"]
    order_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=2000,
    )
    content: str | None = Field(
        default=None,
        min_length=1,
        max_length=2000,
    )
    contact: str | None = Field(
        default=None,
        min_length=3,
        max_length=100,
    )
    client_request_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
