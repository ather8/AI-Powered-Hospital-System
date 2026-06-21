from pydantic import BaseModel, field_validator

# Roles a person may grant themselves at public sign-up. Staff roles
# (doctor, nurse, receptionist, admin) must be assigned by an existing
# admin through a separate, authenticated endpoint — never via open
# self-registration.
SELF_REGISTERABLE_ROLES = {"patient"}

class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str = "patient"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in SELF_REGISTERABLE_ROLES:
            raise ValueError(
                f"role must be one of {sorted(SELF_REGISTERABLE_ROLES)}; "
                "staff roles are assigned by an administrator"
            )
        return v

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str = None  # Optional, only returned if refresh token is generated