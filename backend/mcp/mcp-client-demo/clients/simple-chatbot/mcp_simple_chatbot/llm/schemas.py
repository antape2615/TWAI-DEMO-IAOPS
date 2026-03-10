from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


class DecisionEnvelope(BaseModel):
    decision: Literal["tool", "answer"] = Field(..., description="Elige 'tool' o 'answer'")
    tool: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    answer: Optional[str] = None
    explanation: Optional[str] = None


class IntentEnvelope(BaseModel):
    # 'infrastructure' = crear/gestionar recursos reales AWS via CloudFormation MCP
    intent: Literal["diagram", "text", "both", "infrastructure", "neither"]
    confidence: float = Field(..., ge=0, le=1)
    rationale: Optional[str] = None
