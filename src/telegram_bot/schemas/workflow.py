from pydantic import BaseModel, Field, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

class WorkflowCreateRequest(BaseModel):
    name:str = Field(min_length=1, max_length= 150)
    prompt:str = Field(min_length=5, max_length=3000)
    schedule_time:str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: str = "Asia/Kolkata"
    telegram_enabled: bool = True
    email_enabled: bool = False

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("Invalid timezone.")
        return value


class WorkflowResponse(BaseModel):
    id: int
    name: str
    schedule_time: str
    timezone: str
    enabled: bool

    model_config = {"from_attributes": True}
