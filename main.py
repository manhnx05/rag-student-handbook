import os
import sys
import argparse
import uvicorn
from fastapi import FastAPI
from src.api.routes import router as api_router
from src.services.pipeline import run_full_pipeline, check_graph_store_status, check_vector_store_status
from src.services.rag_service import get_rag_service


def create_app() -> FastAPI:
    """
    Creates and configures the FastAPI application.
    """
    app = FastAPI(
        title="RAG + Graph Student Handbook API",
        description="API for querying the student handbook using RAG + Knowledge Graph",
        version="2.0.0"
    )
    app.include_router(api_router, prefix="/api")
    return app


def main():
    parser = argparse.ArgumentParser(description="RAG + Graph Student Handbook Application")
    parser.add_argument(
        "--mode",
        choices=["api", "ingest", "cli", "status"],
        default="api",
        help="Mode to run: api (start API server), ingest (ingest PDF), cli (interactive query), status (check store status)"
    )
    parser.add_argument(
        "--pdf",
        default="data/raw/handbook.pdf",
        help="Path to PDF file for ingest mode"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for API server"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for API server"
    )
    parser.add_argument(
        "--no-graph",
        action="store_false",
        dest="ingest_graph",
        help="Disable graph ingestion in ingest mode"
    )
    parser.add_argument(
        "--use-graph",
        action="store_true",
        default=True,
        help="Enable graph context in CLI mode (default: True)"
    )
    
    args = parser.parse_args()
    
    if args.mode == "api":
        print(f"Starting API server on {args.host}:{args.port}")
        app = create_app()
        uvicorn.run(app, host=args.host, port=args.port)
    elif args.mode == "ingest":
        run_full_pipeline(args.pdf, ingest_graph=args.ingest_graph)
    elif args.mode == "status":
        check_vector_store_status()
        try:
            check_graph_store_status()
        except Exception:
            print("Graph store not available.")
    elif args.mode == "cli":
        print("RAG + Graph Student Handbook - Interactive Mode")
        print("Type 'quit' or 'exit' to stop.\n")
        
        try:
            rag_service = get_rag_service()
        except Exception as e:
            print(f"Error initializing RAG service: {e}")
            print("Make sure OPENAI_API_KEY is set and the vector store has data.")
            return
        
        while True:
            question = input("\nYour question: ").strip()
            
            if question.lower() in ["quit", "exit"]:
                print("Goodbye!")
                break
            
            if not question:
                continue
            
            try:
                result = rag_service.query(question, use_graph=args.use_graph)
                print("\nAnswer:", result["answer"])
                print("\nVector Sources:")
                for i, source in enumerate(result["vector_sources"], 1):
                    print(f"\n{i}. Source: {source['metadata'].get('source', 'unknown')}, "
                          f"Page: {source['metadata'].get('page', 'unknown')}")
                    print(f"   Distance: {source['distance']:.4f}")
                if result.get("graph_sources"):
                    print("\nGraph Sources:")
                    for i, source in enumerate(result["graph_sources"], 1):
                        print(f"\n{i}. Node: {source['node'].get('name', 'Unknown')}, Score: {source['score']:.4f}")
                        print(f"   Connections: {source['connections']}")
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    main()