from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AIResponse:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    is_fallback: bool = False


class AIProvider(ABC):
    """Every provider (Claude today, OpenAI/Gemini later per ADR-0004) implements this."""

    @abstractmethod
    async def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> AIResponse:
        ...
