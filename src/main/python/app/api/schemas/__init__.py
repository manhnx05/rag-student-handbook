from pydantic import BaseModel, Field

class StudentHandbookQuery(BaseModel):
    query: str = Field(..., description="The query string from the user.")
    session_id: str | None = Field(None, description="Optional session ID for conversation history.")

class StudentHandbookResponse(BaseModel):
    answer: str = Field(..., description="The AI agent's answer.")
    sources: list[str] = Field(default_factory=list, description="List of source documents used.")
