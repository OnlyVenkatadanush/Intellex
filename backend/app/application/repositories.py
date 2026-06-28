from abc import ABC, abstractmethod
from typing import List, Optional
from backend.app.domain.models import (
    UserDomain, SessionDomain, FindingDomain, CitationDomain, DocumentDomain, MemoryDomain
)

class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: str) -> Optional[UserDomain]:
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[UserDomain]:
        pass

    @abstractmethod
    async def create(self, user: UserDomain) -> UserDomain:
        pass


class SessionRepository(ABC):
    @abstractmethod
    async def get_by_id(self, session_id: str) -> Optional[SessionDomain]:
        pass

    @abstractmethod
    async def list_by_user_id(self, user_id: str) -> List[SessionDomain]:
        pass

    @abstractmethod
    async def create(self, session: SessionDomain) -> SessionDomain:
        pass

    @abstractmethod
    async def update(self, session: SessionDomain) -> SessionDomain:
        pass


class FindingRepository(ABC):
    @abstractmethod
    async def create(self, finding: FindingDomain) -> FindingDomain:
        pass

    @abstractmethod
    async def get_by_session_id(self, session_id: str) -> List[FindingDomain]:
        pass


class CitationRepository(ABC):
    @abstractmethod
    async def create(self, citation: CitationDomain) -> CitationDomain:
        pass

    @abstractmethod
    async def get_by_finding_id(self, finding_id: str) -> List[CitationDomain]:
        pass


class DocumentRepository(ABC):
    @abstractmethod
    async def create(self, document: DocumentDomain) -> DocumentDomain:
        pass

    @abstractmethod
    async def list_by_session_id(self, session_id: str) -> List[DocumentDomain]:
        pass


class MemoryRepository(ABC):
    @abstractmethod
    async def create(self, memory: MemoryDomain) -> MemoryDomain:
        pass

    @abstractmethod
    async def search_similarity(self, user_id: str, query_embedding: List[float], limit: int = 5) -> List[MemoryDomain]:
        pass
