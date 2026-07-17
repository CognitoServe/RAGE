import threading

import networkx as nx

from .exceptions import DuplicateFactError, FactNotFoundError
from .interfaces import GraphRepository
from .models import Fact, FactQuery


class NetworkXGraphRepository(GraphRepository):
    def __init__(self):
        # MultiDiGraph allows multiple edges (facts) between the same two nodes
        self._graph = nx.MultiDiGraph()
        # Fast lookup map for edge keys (fact_id) -> (u, v, key)
        self._fact_map: dict[str, tuple[str, str, str]] = {}
        self._lock = threading.Lock()

    def add(self, fact: Fact) -> None:
        with self._lock:
            if fact.fact_id in self._fact_map:
                raise DuplicateFactError(f"Fact with ID {fact.fact_id} already exists.")

            # Nodes are automatically added by NetworkX if they don't exist
            self._graph.add_edge(fact.subject, fact.object, key=fact.fact_id, fact=fact)
            self._fact_map[fact.fact_id] = (fact.subject, fact.object, fact.fact_id)

    def update(self, fact: Fact) -> None:
        with self._lock:
            if fact.fact_id not in self._fact_map:
                raise FactNotFoundError(f"Fact with ID {fact.fact_id} not found.")

            old_u, old_v, key = self._fact_map[fact.fact_id]

            if old_u != fact.subject or old_v != fact.object:
                self._graph.remove_edge(old_u, old_v, key=key)
                if self._graph.degree(old_u) == 0:
                    self._graph.remove_node(old_u)
                if self._graph.degree(old_v) == 0:
                    self._graph.remove_node(old_v)

                self._graph.add_edge(
                    fact.subject, fact.object, key=fact.fact_id, fact=fact
                )
                self._fact_map[fact.fact_id] = (fact.subject, fact.object, fact.fact_id)
            else:
                self._graph.edges[fact.subject, fact.object, key]["fact"] = fact

    def remove(self, fact_id: str) -> None:
        with self._lock:
            if fact_id not in self._fact_map:
                raise FactNotFoundError(f"Fact with ID {fact_id} not found.")

            u, v, key = self._fact_map[fact_id]
            self._graph.remove_edge(u, v, key=key)
            del self._fact_map[fact_id]

            if self._graph.degree(u) == 0:
                self._graph.remove_node(u)
            if self._graph.degree(v) == 0:
                self._graph.remove_node(v)

    def get(self, fact_id: str) -> Fact:
        with self._lock:
            if fact_id not in self._fact_map:
                raise FactNotFoundError(f"Fact with ID {fact_id} not found.")
            u, v, key = self._fact_map[fact_id]
            return self._graph.edges[u, v, key]["fact"]

    def find(self, query: FactQuery) -> list[Fact]:
        results = []
        with self._lock:
            for _u, _v, _key, data in self._graph.edges(keys=True, data=True):
                fact: Fact = data["fact"]

                if query.subject and fact.subject != query.subject:
                    continue
                if query.predicate and fact.predicate != query.predicate:
                    continue
                if query.object and fact.object != query.object:
                    continue
                if query.source and fact.source != query.source:
                    continue
                if (
                    query.min_confidence is not None
                    and fact.confidence < query.min_confidence
                ):
                    continue

                results.append(fact)
        return results

    def get_neighbors(self, entity_id: str) -> list[str]:
        with self._lock:
            if not self._graph.has_node(entity_id):
                return []

            predecessors = list(self._graph.predecessors(entity_id))
            successors = list(self._graph.successors(entity_id))

            return list(set(predecessors + successors))

    def exists(self, fact_id: str) -> bool:
        with self._lock:
            return fact_id in self._fact_map
