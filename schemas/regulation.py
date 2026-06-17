from pydantic import BaseModel, Field, ConfigDict
import uuid
from typing import Optional


class RegulationRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    regulation_code: str
    rule_text: Optional[str]


class RegulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    regulation_code: str
    name: str
    rules: list[RegulationRuleResponse] = Field(default_factory=list)
