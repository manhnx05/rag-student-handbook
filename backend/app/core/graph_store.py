from neo4j import GraphDatabase, exceptions
from src.config import settings
from typing import List, Dict, Any, Optional
from langchain_neo4j import Neo4jGraph


class GraphStore:
    def __init__(self):
        self.uri = settings.NEO4J_URI
        self.username = settings.NEO4J_USERNAME
        self.password = settings.NEO4J_PASSWORD
        self.database = settings.NEO4J_DATABASE
        self.driver = None
        self.graph = None
        self._connect()
    
    def _connect(self):
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            self.driver.verify_connectivity()
            self.graph = Neo4jGraph(
                url=self.uri,
                username=self.username,
                password=self.password,
                database=self.database
            )
            print(f"Connected to Neo4j at {self.uri}")
        except exceptions.Neo4jError as e:
            print(f"Neo4j connection error: {e}")
            raise
        except Exception as e:
            print(f"Error connecting to Neo4j: {e}")
            raise
    
    def close(self):
        if self.driver:
            self.driver.close()
            print("Disconnected from Neo4j")
    
    def add_entities(self, entities: List[Dict[str, Any]]):
        """Add entities to the graph."""
        if not entities:
            return 0
        
        with self.driver.session(database=self.database) as session:
            count = 0
            for entity in entities:
                try:
                    entity_type = entity.get("type", "Entity")
                    entity_name = entity.get("name")
                    if not entity_name:
                        continue
                    
                    session.run(
                        f"MERGE (e:{entity_type} {{name: $name}}) "
                        "SET e += $props",
                        name=entity_name,
                        props=entity.get("properties", {})
                    )
                    count += 1
                except Exception as e:
                    print(f"Error adding entity {entity}: {e}")
            
            print(f"Added {count} entities to graph")
            return count
    
    def add_relationships(self, relationships: List[Dict[str, Any]]):
        """Add relationships to the graph."""
        if not relationships:
            return 0
        
        with self.driver.session(database=self.database) as session:
            count = 0
            for rel in relationships:
                try:
                    source = rel.get("source")
                    target = rel.get("target")
                    rel_type = rel.get("type", "RELATED_TO")
                    if not source or not target:
                        continue
                    
                    session.run(
                        "MATCH (a {name: $source}), (b {name: $target}) "
                        f"MERGE (a)-[r:{rel_type}]->(b) "
                        "SET r += $props",
                        source=source,
                        target=target,
                        props=rel.get("properties", {})
                    )
                    count += 1
                except Exception as e:
                    print(f"Error adding relationship {rel}: {e}")
            
            print(f"Added {count} relationships to graph")
            return count
    
    def query_graph(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Query the graph for relevant information."""
        try:
            results = self.graph.query(
                """
                CALL db.index.fulltext.queryNodes("entityIndex", $query) 
                YIELD node, score
                OPTIONAL MATCH (node)-[r]-(neighbor)
                RETURN node, score, collect(DISTINCT {relation: type(r), neighbor: neighbor.name}) as connections
                ORDER BY score DESC
                LIMIT $top_k
                """,
                {"query": query, "top_k": top_k}
            )
            
            formatted = []
            for record in results:
                formatted.append({
                    "node": dict(record["node"]),
                    "score": record.get("score", 0),
                    "connections": record.get("connections", [])
                })
            return formatted
        except Exception as e:
            print(f"Error querying graph: {e}")
            return []
    
    def clear_graph(self):
        """Clear all nodes and relationships from the graph."""
        with self.driver.session(database=self.database) as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("Cleared all nodes and relationships from graph")
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the graph."""
        with self.driver.session(database=self.database) as session:
            node_result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = node_result.single()["count"]
            
            rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = rel_result.single()["count"]
            
            return {
                "node_count": node_count,
                "relationship_count": rel_count
            }
    
    def create_entity_index(self):
        """Create a full-text index for entities."""
        with self.driver.session(database=self.database) as session:
            try:
                session.run(
                    "CREATE FULLTEXT INDEX entityIndex IF NOT EXISTS FOR (n:Entity|Person|Organization|Document|Topic|Rule|Policy) ON EACH [n.name]"
                )
                print("Created full-text index for entities")
            except Exception as e:
                print(f"Index already exists or error: {e}")


_graph_store_instance: Optional[GraphStore] = None


def get_graph_store() -> GraphStore:
    """Get the singleton GraphStore instance."""
    global _graph_store_instance
    if _graph_store_instance is None:
        _graph_store_instance = GraphStore()
    return _graph_store_instance
