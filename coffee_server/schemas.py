"""Request/response shapes for the /v1/ask endpoint."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class AskRequest(BaseModel):
    provider: Literal["anthropic", "qwen"]
    prompt: Optional[str] = None
    messages: Optional[list[ChatMessage]] = None
    system: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = Field(default=None, gt=0, le=32768)

    @model_validator(mode="after")
    def _exactly_one_of_prompt_or_messages(self) -> "AskRequest":
        if bool(self.prompt) == bool(self.messages):
            raise ValueError("provide exactly one of 'prompt' or 'messages'")
        return self


class AskResponse(BaseModel):
    provider: str
    model: str
    content: str
