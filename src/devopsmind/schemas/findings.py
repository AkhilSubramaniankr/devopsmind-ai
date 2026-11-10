from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class Finding(BaseModel):
    id: str
    run_id: str
    agent_name: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    file_path: str
    line_number: Optional[int] = None
    title: str
    description: str
    recommended_fix: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())