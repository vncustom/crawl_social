from pydantic import BaseModel, Field


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
