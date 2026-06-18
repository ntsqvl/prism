from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict


class EnterpriseRegisterRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "TechCorp Philippines Inc.",
                "country_code": "PH",
                "industry_code": "banking",
            }
        }
    )

    name: str = Field(..., min_length=2, max_length=255)
    country_code: str = Field(..., min_length=2, max_length=10)
    industry_code: str = Field(..., min_length=2, max_length=50)

    @field_validator("name")
    def name_must_not_be_blank(cls, v):
        if not v.strip():
            raise ValueError("Company name cannot be blank.")
        return v.strip()

    @field_validator("country_code")
    def clean_country_code(cls, v):
        return v.strip().upper()

    @field_validator("industry_code")
    def clean_industry_code(cls, v):
        return v.strip().lower()


class EnterpriseRegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enterprise_id: str
    name: str
    country_code: str
    industry_code: str
    country_label: str
    industry_label: str
    created_at: datetime
    message: str


class DropdownOption(BaseModel):
    code: str
    label: str


class EnterpriseOptionsResponse(BaseModel):
    countries: list[DropdownOption]
    industries: list[DropdownOption]


class EnterpriseGetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enterprise_id: str
    name: str
    country_code: str
    industry_code: str
    country_label: str
    industry_label: str
    created_at: datetime