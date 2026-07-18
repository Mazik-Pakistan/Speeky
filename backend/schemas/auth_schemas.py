import re
from pydantic import BaseModel, EmailStr, Field, field_validator


def _require_email_format(v: str) -> str:
    if not v.lower().endswith(("@gmail.com", "@outlook.com")):
        raise ValueError("Only Gmail and Outlook email addresses are allowed")
    return v

def validate_password(v: str) -> str:
    if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$" , v):
        raise ValueError("Password must be 8+ characters long and contain at least one uppercase letter, one lowercase letter, one digit, and one special character.")
    return v
    
class SignupSchema(BaseModel):
    email: EmailStr
    password: str
    name: str = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9 _-]+$")

    _validate_gmail = field_validator("email")(_require_email_format)
    _validate_password = field_validator("password")(validate_password)


class LoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

    _validate_gmail = field_validator("email")(_require_email_format)
    

class ForgotSchema(BaseModel):
    email: EmailStr

    _validate_gmail = field_validator("email")(_require_email_format)


class ResendOtpSchema(ForgotSchema):
    """Same shape as ForgotSchema (email only) — separate type for endpoint clarity."""


class ResetSchema(BaseModel):
    token: str = Field(min_length=1)
    password: str

    _validate_password = field_validator("password")(validate_password)


class VerifyOtpSchema(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")

    _validate_gmail = field_validator("email")(_require_email_format)