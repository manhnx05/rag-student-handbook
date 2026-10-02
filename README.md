# Student Handbook Hybrid RAG

Vietnamese student-handbook assistant using Gemini, Qdrant, Neo4j, PostgreSQL,
FastAPI, and a small Streamlit UI.

## Project layout

```text
.
├── src/
│   ├── main/python/app/
│   │   ├── api/                 # FastAPI routes and application entry point
│   │   ├── config/              # Runtime settings
│   │   ├── rag/
│   │   │   ├── ingestion/       # PDF loading and graph extraction
│   │   │   ├── splitters/       # Page-aware semantic chunking
│   │   │   ├── embeddings/      # Gemini embeddings
│   │   │   ├── vectorstore/     # Qdrant vector store
│   │   │   ├── knowledge_graph/ # Neo4j graph store
│   │   │   ├── keyword_search/  # BM25 scoring
│   │   │   ├── retrievers/      # Hybrid retrieval and reranking
│   │   │   ├── chains/          # LangGraph CRAG workflow
│   │   │   ├── prompts/         # RAG prompt templates
│   │   │   ├── llm/             # Gemini chat model
│   │   │   └── tools/           # Agent search tools
│   │   ├── services/            # Chat, ingestion, and RAG orchestration
│   │   ├── db/                  # PostgreSQL chat history
│   │   ├── utils/               # Logging and application exceptions
│   │   └── workers/             # Background workers
│   └── alembic/                 # PostgreSQL migrations
├── tests/                       # Unit and API tests
├── data/                        # Raw, processed, and evaluation data
├── cli/                         # CLI tools and scripts
├── frontend/                    # Streamlit frontend app
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── requirements.txt
```

## Run locally

1. Create a `.env` from `.env.example` and configure `GEMINI_API_KEY` and the
   database/service credentials.
2. Install dependencies with `pip install -r requirements.txt`.
3. Start the API from the repository root:

   ```powershell
   $env:PYTHONPATH = "src/main/python"
   alembic upgrade head
   uvicorn app.api.main:app --reload --app-dir src/main/python
   ```

4. In another terminal, start the UI:

   ```powershell
   streamlit run frontend/streamlit_app.py
   ```

   Set `API_BASE_URL=http://localhost:8000` in the environment for the UI.
5. Start the Celery worker for PDF uploads:

   ```powershell
   $env:PYTHONPATH = "src/main/python"
   celery -A app.workers.celery_worker.celery_app worker --loglevel=info
   ```

For the full stack, run `docker compose up --build`. Open Streamlit at
`http://localhost:8501` and the API documentation at `http://localhost:8000/docs`.

The chat and upload API is intentionally unauthenticated for a local,
single-user setup. Do not expose these services publicly without adding
authentication and per-user session isolation.
