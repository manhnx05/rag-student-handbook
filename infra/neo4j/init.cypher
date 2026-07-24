// ---------------------------------------------------------------------------
// Neo4j initialisation for Student Handbook RAG
//
// This script runs once when the Neo4j container starts for the first time.
// It creates uniqueness constraints and indexes for the entity types that
// the knowledge-graph pipeline stores.
// ---------------------------------------------------------------------------

// -- Uniqueness constraints -------------------------------------------------

CREATE CONSTRAINT entity_name_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.name IS UNIQUE;

CREATE CONSTRAINT person_name_unique IF NOT EXISTS
FOR (p:Person) REQUIRE p.name IS UNIQUE;

CREATE CONSTRAINT organization_name_unique IF NOT EXISTS
FOR (o:Organization) REQUIRE o.name IS UNIQUE;

CREATE CONSTRAINT department_name_unique IF NOT EXISTS
FOR (d:Department) REQUIRE d.name IS UNIQUE;

CREATE CONSTRAINT topic_name_unique IF NOT EXISTS
FOR (t:Topic) REQUIRE t.name IS UNIQUE;

CREATE CONSTRAINT rule_name_unique IF NOT EXISTS
FOR (r:Rule) REQUIRE r.name IS UNIQUE;

CREATE CONSTRAINT policy_name_unique IF NOT EXISTS
FOR (p:Policy) REQUIRE p.name IS UNIQUE;

CREATE CONSTRAINT document_name_unique IF NOT EXISTS
FOR (d:Document) REQUIRE d.name IS UNIQUE;

// -- Full-text search index (used by GraphStore.query_graph) ----------------
CREATE FULLTEXT INDEX entityIndex IF NOT EXISTS
FOR (n:Entity|Person|Organization|Document|Topic|Rule|Policy|Department)
ON EACH [n.name];
