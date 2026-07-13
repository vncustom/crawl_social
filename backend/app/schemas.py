from datetime import date

from pydantic import BaseModel, Field, model_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class AuthResponse(BaseModel):
    username: str
    role: str
    csrf_token: str


class CurrentAdminResponse(BaseModel):
    username: str
    role: str


class PageCreate(BaseModel):
    page_id: str = Field(pattern=r"^[0-9]+$", max_length=64)
    display_name: str | None = Field(default=None, max_length=255)
    enabled: bool = True
    daily_sync_enabled: bool = True
    backfill_start: date | None = None
    backfill_end: date | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if (self.backfill_start is None) != (self.backfill_end is None):
            raise ValueError("Phải nhập cả ngày bắt đầu và ngày kết thúc backfill.")
        if self.backfill_start and self.backfill_start > self.backfill_end:
            raise ValueError("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")
        return self


class PageUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    enabled: bool | None = None
    daily_sync_enabled: bool | None = None


class BackfillRequest(BaseModel):
    start_date: date
    end_date: date
