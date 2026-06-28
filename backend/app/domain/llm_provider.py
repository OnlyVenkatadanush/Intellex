from abc import ABC, abstractmethod
from typing import Type, TypeVar
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class LLMProvider(ABC):
    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> str:
        """
        Generate unstructured text content.
        """
        pass

    @abstractmethod
    async def generate_structured(self, prompt: str, system_prompt: str, response_model: Type[T], temperature: float = 0.2) -> T:
        """
        Generate structured output complying to a Pydantic schema model.
        """
        pass
