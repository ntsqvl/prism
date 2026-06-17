from sqlalchemy.orm import Session
from models.enterprise import EnterpriseModel
from schemas.enterprise import DropdownOption, EnterpriseOptionsResponse
import uuid


# Dropdown definitions (source of truth for the registration form)
COUNTRY_OPTIONS = [
    {"code": "PH", "label": "Philippines"},
    {"code": "US", "label": "United States"},
    {"code": "GB", "label": "United Kingdom"},
    {"code": "SG", "label": "Singapore"},
    {"code": "AU", "label": "Australia"},
    {"code": "JP", "label": "Japan"},
    {"code": "IN", "label": "India"},
    {"code": "DE", "label": "Germany"},
    {"code": "EU", "label": "European Union"},
    {"code": "CA", "label": "Canada"},
    {"code": "MY", "label": "Malaysia"},
    {"code": "ID", "label": "Indonesia"},
    {"code": "TH", "label": "Thailand"},
    {"code": "VN", "label": "Vietnam"},
    {"code": "OT", "label": "Other"},
]

INDUSTRY_OPTIONS = [
    {"code": "banking",        "label": "Banking & Financial Services"},
    {"code": "telco",          "label": "Telecommunications"},
    {"code": "healthcare",     "label": "Healthcare"},
    {"code": "insurance",      "label": "Insurance"},
    {"code": "logistics",      "label": "Logistics & Supply Chain"},
    {"code": "retail",         "label": "Retail & E-Commerce"},
    {"code": "manufacturing",  "label": "Manufacturing"},
    {"code": "government",     "label": "Government & Public Sector"},
    {"code": "education",      "label": "Education"},
    {"code": "energy",         "label": "Energy & Utilities"},
    {"code": "real_estate",    "label": "Real Estate & Construction"},
    {"code": "media",          "label": "Media & Entertainment"},
    {"code": "technology",     "label": "Technology & Software"},
    {"code": "consulting",     "label": "Professional Services & Consulting"},
    {"code": "other",          "label": "Other"},
]


def get_options() -> EnterpriseOptionsResponse:
    return EnterpriseOptionsResponse(
        countries=[DropdownOption(**c) for c in COUNTRY_OPTIONS],
        industries=[DropdownOption(**i) for i in INDUSTRY_OPTIONS],
    )


def resolve_country_label(code: str) -> str:
    for c in COUNTRY_OPTIONS:
        if c["code"] == code.upper():
            return c["label"]
    return f"Other ({code})"


def resolve_industry_label(code: str) -> str:
    for i in INDUSTRY_OPTIONS:
        if i["code"] == code.lower():
            return i["label"]
    return f"Other ({code})"


def check_duplicate_enterprise(db: Session, name: str, country_code: str) -> bool:
    existing = db.query(EnterpriseModel).filter(
        EnterpriseModel.name == name.strip(),
        EnterpriseModel.country_code == country_code.upper()
    ).first()
    return existing is not None


def create_enterprise(db: Session, name: str, country_code: str, industry_code: str) -> EnterpriseModel:
    new = EnterpriseModel(
        enterprise_id = uuid.uuid4(),
        name = name.strip(),
        country_code = country_code.strip().upper(),
        industry_code = industry_code.strip().lower(),
    )
    db.add(new)
    db.commit()
    db.refresh(new)
    return new


def get_enterprise(db: Session, enterprise_id) -> EnterpriseModel | None:
    return db.query(EnterpriseModel).filter(EnterpriseModel.enterprise_id == enterprise_id).first()


def search_enterprises_by_name(db: Session, name: str) -> list[EnterpriseModel]:
    """Case-insensitive partial match search for enterprise name."""
    pattern = f"%{name.strip()}%"
    return db.query(EnterpriseModel).filter(EnterpriseModel.name.ilike(pattern)).order_by(EnterpriseModel.created_at.desc()).all()
