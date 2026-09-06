-- ---------------------------------------------------------------------------
-- PostgreSQL initialisation for Student Handbook RAG
--
-- NOTE: Application tables (users, chat_sessions, chat_messages) are managed
--       by Alembic migrations and are NOT created here.  This script only
--       installs extensions that Alembic cannot install itself.
-- ---------------------------------------------------------------------------

-- UUID generation support (used by SQLAlchemy models via uuid_generate_v4())
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
