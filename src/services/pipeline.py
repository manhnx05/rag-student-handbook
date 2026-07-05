import os
import json
from src.core.ingestor import ingest_pdf, ingest_chunks_from_json
from src.core.vector_store import get_vector_store
from src.core.graph_store import get_graph_store
from src.core.extractor import extract_from_chunks


def run_full_pipeline(pdf_path: str, clear_existing: bool = True, ingest_graph: bool = True):
    """
    Runs the full RAG pipeline:
    1. Process PDF into chunks
    2. Save chunks to JSON
    3. Ingest chunks into vector store
    4. Extract entities/relationships and ingest into graph (optional)
    """
    # Create output directory if it doesn't exist
    output_dir = "data/processed"
    os.makedirs(output_dir, exist_ok=True)
    output_json = os.path.join(output_dir, "chunks.json")
    
    print("=" * 50)
    print("Starting Full RAG + Graph Pipeline")
    print("=" * 50)
    
    # Step 1: Process PDF and save chunks
    from src.core.chunker import process_pdf_to_chunks
    chunks = process_pdf_to_chunks(pdf_path)
    
    print(f"\nSaving chunks to {output_json}...")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=4)
    print("Chunks saved successfully.")
    
    # Step 2: Ingest into vector store
    print("\nIngesting chunks into vector store...")
    num_ingested = ingest_pdf(pdf_path, clear_existing=clear_existing)
    
    # Step 3: Extract and ingest into graph (optional)
    if ingest_graph:
        try:
            print("\nExtracting entities and relationships...")
            extraction_result = extract_from_chunks(chunks)
            
            print("\nIngesting into graph store...")
            graph_store = get_graph_store()
            if clear_existing:
                graph_store.clear_graph()
            graph_store.create_entity_index()
            entity_count = graph_store.add_entities(extraction_result["entities"])
            rel_count = graph_store.add_relationships(extraction_result["relationships"])
            print(f"Ingested {entity_count} entities and {rel_count} relationships.")
        except Exception as e:
            print(f"Graph ingestion error: {e}")
    
    print("\n" + "=" * 50)
    print(f"Pipeline Complete! Ingested {num_ingested} chunks.")
    print("=" * 50)


def check_vector_store_status():
    """
    Prints the current status of the vector store.
    """
    vector_store = get_vector_store()
    count = vector_store.count()
    print(f"Vector store contains {count} chunks.")
    return count


def check_graph_store_status():
    """
    Prints the current status of the graph store.
    """
    try:
        graph_store = get_graph_store()
        stats = graph_store.get_stats()
        print(f"Graph store contains {stats['node_count']} nodes and {stats['relationship_count']} relationships.")
        return stats
    except Exception as e:
        print(f"Graph store error: {e}")
        return {"node_count": 0, "relationship_count": 0}
