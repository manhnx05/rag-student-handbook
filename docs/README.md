
# Medi-Chatbot

Hệ thống chatbot y tế sử dụng RAG với kiến trúc:
- Postgres: Lưu dữ liệu bệnh nhân và khám bệnh
- Neo4j: Lưu đồ thị kiến thức
- Qdrant: Vector DB cho tìm kiếm ngữ nghĩa
- FastAPI: Backend API
- Next.js: Frontend

## Cách chạy

1. Sao chép `.env.example` thành `.env` và điền thông tin
2. Chạy: `docker-compose up -d`
3. Truy cập: `http://localhost:3000`
