from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class SignupSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, 
        # pattern=r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).+$"
    )
    name: Optional[str] = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9 _-]+$")

class LoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class ForgotSchema(BaseModel):
    email: EmailStr


class ResetSchema(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=8,
        # pattern=r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).+$"                          
    )