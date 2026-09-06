
# Student Handbook Hybrid RAG

Chatbot RAG cho sổ tay sinh viên, kết hợp tìm kiếm vector trên Qdrant,
knowledge graph trên Neo4j và sinh câu trả lời bằng Gemini.

## Cấu trúc chính

- `backend/app/api`: REST API và dependencies
- `backend/app/core`: cấu hình, logging, database và security
- `backend/app/ingestion`: đọc PDF, chunking và ingestion pipeline
- `backend/app/embedding`: embedding model
- `backend/app/vector_store`: Qdrant client và vector store
- `backend/app/knowledge_graph`: Neo4j store và graph operations
- `backend/app/retrieval`: hybrid retrieval và LangGraph agent
- `backend/app/llm`: LLM factory và prompts
- `backend/app/keyword_search`: package dành cho BM25
- `backend/app/citation`: package dành cho citation nguồn
- `backend/app/services`: auth, chat và ingestion services

## Cách chạy

1. Sao chép `.env.example` thành `.env` và điền các secret cần thiết.
2. Chạy `docker compose up -d --build`.
3. Truy cập `http://localhost:8080` qua Nginx.

Chạy backend trực tiếp từ thư mục `backend`:

```powershell
$env:PYTHONPATH = "."
uvicorn app.api.main:app --reload
```

Chạy test:

```powershell
python -m pytest
```
