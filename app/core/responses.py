from pydantic import BaseModel


class ErrorInfo(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel):
    success: bool
    data: dict | None = None
    error: ErrorInfo | None = None