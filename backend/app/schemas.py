from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

Name = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=140, pattern=r"^[^\r\n]+$"
    ),
]
Short = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=250, pattern=r"^[^\r\n]*$")
]
Password = Annotated[str, Field(min_length=12, max_length=128)]
Body = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=15000)
]


class Address(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.lower()


class Register(Address):
    name: Name
    password: Password


class Login(Address):
    password: str = Field(min_length=1, max_length=128)
    remember: bool = False


class Profile(Address):
    name: Name


class PasswordChange(BaseModel):
    current: str = Field(max_length=128)
    password: Password


class UserView(Profile):
    model_config = ConfigDict(from_attributes=True)
    id: int


class SessionView(BaseModel):
    user: UserView
    csrf: str


class ContactIn(Address):
    name: Short = ""
    company: Short = ""
    role: Short = ""
    source: Short = "Manual"
    status: Literal["New", "Contacted", "Replied"] = "New"


class ImportIn(BaseModel):
    contacts: list[ContactIn] = Field(min_length=1, max_length=1000)
    batch: Short = "Import"


class ImportReviewIn(BaseModel):
    contacts: list[dict[str, str]] = Field(min_length=1, max_length=1000)


class TemplateIn(BaseModel):
    name: Name
    subject: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=300, pattern=r"^[^\r\n]+$"
        ),
    ]
    body: Body


class CampaignIn(TemplateIn):
    resume_id: int | None = None
    tracking_open: bool = False
    tracking_click: bool = False


class TrackingPreferences(BaseModel):
    tracking_open: bool = False
    tracking_click: bool = False


class SendRequest(BaseModel):
    campaign_id: int
    contact_ids: list[int] = Field(min_length=1, max_length=20)
    confirm: bool = False


class Reply(BaseModel):
    request_id: UUID
    body: Body
