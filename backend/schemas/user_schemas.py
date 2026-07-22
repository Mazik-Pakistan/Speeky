from typing import Literal, Optional
from schemas.auth_schemas import _require_email_format
from pydantic import BaseModel, EmailStr, Field, model_validator, field_validator


class UpdateProfileSchema(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9 _-]+$")
    email: Optional[EmailStr] = None

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.name is None and self.email is None:
            raise ValueError("At least one of name or email must be provided")
        return self

    _validate_gmail = field_validator("email")(_require_email_format)


class UpdateRoleSchema(BaseModel):
    role: Literal["USER", "ADMIN"]


class DeleteAccountSchema(BaseModel):
    password: str = Field(min_length=1)
