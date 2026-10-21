# Student Handbook Hybrid RAG

Vietnamese student-handbook assistant using Qdrant, Neo4j, PostgreSQL, FastAPI,
and a small Streamlit UI. Embeddings run locally with a Vietnamese
sentence-transformers model, so only the answer/grading LLM calls the Gemini API.

## Project layout

```text
.
├── backend/
│   ├── api/                     # FastAPI routes, schemas, rate limiting
│   ├── chunking/               # Page-aware markdown chunking
│   ├── db/                     # PostgreSQL chat history (SQLAlchemy async)
│   ├── embeddings/             # Local Vietnamese embeddings (sentence-transformers)
│   ├── evaluation/             # Retrieval evaluation harness
│   ├── ingestion/              # PDF loading and graph extraction
│   ├── llm/
│   │   ├── chains/             # LangGraph CRAG workflow
│   │   └── tools/              # Agent search tools
│   ├── prompts/                # RAG prompt templates
│   ├── retrieval/              # Hybrid retrieval (Qdrant + BM25 + Neo4j), citation
│   ├── services/               # Chat, ingestion, guardrails, orchestration
│   ├── utils/                  # Logging and application exceptions
│   ├── vectordb/               # Qdrant vector store
│   ├── workers/                # Celery worker for PDF ingestion
│   └── config.py               # Runtime settings
├── alembic/                     # PostgreSQL migrations
├── frontend/                    # Streamlit frontend app
├── data/                        # Raw, processed, and evaluation data
├── tests/                       # Unit and API tests
├── main.py                      # FastAPI application entrypoint
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

## Run locally

1. Create a `.env` from `.env.example` and configure `GEMINI_API_KEY` and the
   database/service credentials.
2. Install dependencies with `uv sync`.
3. Start the infrastructure (PostgreSQL, Redis, Qdrant, Neo4j):

   ```powershell
   docker compose up -d postgres redis qdrant neo4j
   ```

4. Run the migrations and start the API from the repository root:

   ```powershell
   uv run alembic upgrade head
   uv run uvicorn main:app --reload
   ```

5. In another terminal, start the UI (headless avoids the first-run email prompt):

   ```powershell
   uv run streamlit run frontend/streamlit_app.py --server.headless true
   ```

   Set `API_BASE_URL=http://localhost:8000` in the environment for the UI.

6. Start the Celery worker for PDF uploads:

   ```powershell
   uv run celery -A backend.workers.celery_worker.celery_app worker --loglevel=info
   ```

For the full stack, run `docker compose up --build`. Open Streamlit at
`http://localhost:8501` and the API documentation at `http://localhost:8000/docs`.

## Evaluation

Measure retrieval quality against the ground truth in `data/evaluation`:

```powershell
uv run python -m backend.evaluation.harness --mode both
```

Use `--mode dense` or `--mode hybrid` to compare dense-only retrieval against
the hybrid (vector + BM25 + graph) pipeline.

The chat and upload API is intentionally unauthenticated for a local,
single-user setup. Do not expose these services publicly without adding
authentication and per-user session isolation.
