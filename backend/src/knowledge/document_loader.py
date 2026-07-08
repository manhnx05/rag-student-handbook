from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from backend.src.core.config import settings
from typing import List, Dict, Any
from pydantic import BaseModel, Field


class Entity(BaseModel):
    name: str = Field(description="The name of the entity")
    type: str = Field(description="The type of the entity (e.g., Person, Organization, Topic, Rule, Document, Policy, Department)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties of the entity")


class Relationship(BaseModel):
    source: str = Field(description="The name of the source entity")
    target: str = Field(description="The name of the target entity")
    type: str = Field(description="The type of the relationship (e.g., HAS_POLICY, BELONGS_TO, DEFINES, RELATED_TO)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties of the relationship")


class ExtractionResult(BaseModel):
    entities: List[Entity] = Field(description="List of extracted entities")
    relationships: List[Relationship] = Field(description="List of extracted relationships")


def extract_entities_and_relationships(text: str) -> ExtractionResult:
    """Extract entities and relationships from text using LLM."""
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert at extracting entities and relationships from text.
Extract all relevant entities and relationships from the given text.
Entity types should include: Person, Organization, Department, Topic, Rule, Policy, Document, Process.
Relationship types should include: HAS_POLICY, BELONGS_TO, DEFINES, RELATED_TO, GOVERNS, REQUIRES, IMPLEMENTS.
Return only the JSON output without any additional text."""),
        ("human", "{text}")
    ])
    
    parser = JsonOutputParser(pydantic_object=ExtractionResult)
    
    chain = prompt | llm | parser
    
    try:
        result = chain.invoke({"text": text})
        return ExtractionResult(**result)
    except Exception as e:
        print(f"Error extracting entities/relationships: {e}")
        return ExtractionResult(entities=[], relationships=[])


def extract_from_chunks(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract entities and relationships from a list of chunks."""
    all_entities: List[Dict] = []
    all_relationships: List[Dict] = []
    
    for i, chunk in enumerate(chunks):
        print(f"Extracting from chunk {i+1}/{len(chunks)}...")
        content = chunk.get("content", "")
        result = extract_entities_and_relationships(content)
        
        for entity in result.entities:
            entity_dict = entity.model_dump()
            if "source_chunk" not in entity_dict["properties"]:
                entity_dict["properties"]["source_chunk"] = chunk.get("id")
            all_entities.append(entity_dict)
        
        for rel in result.relationships:
            rel_dict = rel.model_dump()
            if "source_chunk" not in rel_dict["properties"]:
                rel_dict["properties"]["source_chunk"] = chunk.get("id")
            all_relationships.append(rel_dict)
    
    # Deduplicate entities
    seen = set()
    unique_entities = []
    for entity in all_entities:
        key = (entity["name"], entity["type"])
        if key not in seen:
            seen.add(key)
            unique_entities.append(entity)
    
    # Deduplicate relationships
    seen_rels = set()
    unique_relationships = []
    for rel in all_relationships:
        key = (rel["source"], rel["target"], rel["type"])
        if key not in seen_rels:
            seen_rels.add(key)
            unique_relationships.append(rel)
    
    return {
        "entities": unique_entities,
        "relationships": unique_relationships
    }
