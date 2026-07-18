New-Item -ItemType Directory -Force src\knowledge\graph | Out-Null
New-Item -ItemType Directory -Force src\knowledge\evidence | Out-Null
New-Item -ItemType Directory -Force src\knowledge\entities | Out-Null

@"
from dataclasses import dataclass

@dataclass(slots=True)
class Entity:

    id: str
    type: str
    name: str
"@ | Set-Content src\knowledge\entities\entity.py -Encoding UTF8

@"
from dataclasses import dataclass

@dataclass(slots=True)
class Evidence:

    source: str
    confidence: float
    timestamp: str
    description: str
"@ | Set-Content src\knowledge\evidence\evidence.py -Encoding UTF8

@"
import networkx as nx

class KnowledgeGraph:

    def __init__(self):

        self.graph = nx.DiGraph()

    def add_entity(self, entity):

        self.graph.add_node(
            entity.id,
            type=entity.type,
            name=entity.name
        )

    def add_relation(self, source, target, relation):

        self.graph.add_edge(
            source,
            target,
            relation=relation
        )

    def node_count(self):

        return self.graph.number_of_nodes()

    def edge_count(self):

        return self.graph.number_of_edges()
"@ | Set-Content src\knowledge\graph\knowledge_graph.py -Encoding UTF8

@"
from src.knowledge.graph.knowledge_graph import KnowledgeGraph
from src.knowledge.entities.entity import Entity

graph = KnowledgeGraph()

gold = Entity(
    id="gold",
    type="asset",
    name="Gold"
)

graph.add_entity(gold)

print("Nodes:", graph.node_count())
print("Edges:", graph.edge_count())
"@ | Set-Content src\main.py -Encoding UTF8
