"""Data schemas for natural language parsing and intent extraction."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ParsedWorkflowIntent:
    intent: str
    operations: List[str]
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    explanation: str = ""
    reasoning: str = ""
    is_supported: bool = True
    unsupported_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "operations": self.operations,
            "parameters": self.parameters,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "reasoning": self.reasoning,
            "is_supported": self.is_supported,
            "unsupported_reason": self.unsupported_reason,
        }
