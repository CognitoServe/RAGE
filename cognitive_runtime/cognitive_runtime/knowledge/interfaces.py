from abc import ABC, abstractmethod

from .models import Fact, FactQuery


class GraphRepository(ABC):
    @abstractmethod
    def add(self, fact: Fact) -> None:
        pass

    @abstractmethod
    def update(self, fact: Fact) -> None:
        pass

    @abstractmethod
    def remove(self, fact_id: str) -> None:
        pass

    @abstractmethod
    def get(self, fact_id: str) -> Fact:
        pass

    @abstractmethod
    def find(self, query: FactQuery) -> list[Fact]:
        pass

    @abstractmethod
    def get_neighbors(self, entity_id: str) -> list[str]:
        pass

    @abstractmethod
    def exists(self, fact_id: str) -> bool:
        pass


class KnowledgeSystem(ABC):
    @abstractmethod
    def add_fact(self, fact: Fact) -> None:
        pass

    @abstractmethod
    def update_fact(self, fact: Fact) -> None:
        pass

    @abstractmethod
    def remove_fact(self, fact_id: str) -> None:
        pass

    @abstractmethod
    def get_fact(self, fact_id: str) -> Fact:
        pass

    @abstractmethod
    def find(self, query: FactQuery) -> list[Fact]:
        pass

    @abstractmethod
    def neighbors(self, entity_id: str) -> list[str]:
        pass

    @abstractmethod
    def exists(self, fact_id: str) -> bool:
        pass
