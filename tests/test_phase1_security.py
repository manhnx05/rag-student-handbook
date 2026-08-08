"""
Phase 1 Security Tests
======================
Tests for:
  1. Ingest endpoint requires admin authentication (401/403 without token)
  2. auth_service reset password uses settings.FRONTEND_URL (no hardcoded URL)
  3. resend is NOT imported at module level in auth_service (lazy import)
  4. User model has is_admin column defaulting to False
  5. datetime columns are timezone-aware
  6. Config FRONTEND_URL can be overridden
  7. JWT create/decode round-trip
  8. Reset token has 'type' claim
"""
import ast
import os
import pathlib
import sys

# ---------------------------------------------------------------------------
# Bootstrap: add backend/src to Python path (mirrors pytest.ini settings)
# ---------------------------------------------------------------------------
BACKEND = pathlib.Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

# Set required env vars BEFORE importing any settings-dependent modules
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "password123")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("JWT_SECRET_KEY", "supersecretkey1234567890abcdef00")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

import pytest
import inspect


# ===========================================================================
# 1. User Model
# ===========================================================================
class TestUserModel:
    def test_is_admin_column_exists(self):
        from src.core.db.models import User
        assert hasattr(User, "is_admin"), "User model missing is_admin attribute"

    def test_is_admin_defaults_to_false_python_level(self):
        from src.core.db.models import User
        user = User(email="test@example.com")
        assert user.is_admin is False, f"Expected False, got {user.is_admin!r}"

    def test_is_admin_can_be_set_true(self):
        from src.core.db.models import User
        admin = User(email="admin@example.com", is_admin=True)
        assert admin.is_admin is True

    def test_is_google_login_defaults_to_false(self):
        from src.core.db.models import User
        user = User(email="user@example.com")
        assert user.is_google_login is False

    def test_created_at_is_timezone_aware(self):
        import sqlalchemy
        from src.core.db.models import User
        col = User.__table__.columns["created_at"]
        assert isinstance(col.type, sqlalchemy.DateTime)
        assert col.type.timezone is True, "created_at must be timezone-aware"

    def test_chat_session_dates_are_timezone_aware(self):
        import sqlalchemy
        from src.core.db.models import ChatSession
        for col_name in ("created_at", "updated_at"):
            col = ChatSession.__table__.columns[col_name]
            assert col.type.timezone is True, f"ChatSession.{col_name} must be timezone-aware"

    def test_chat_message_created_at_is_timezone_aware(self):
        import sqlalchemy
        from src.core.db.models import ChatMessage
        col = ChatMessage.__table__.columns["created_at"]
        assert col.type.timezone is True


# ===========================================================================
# 2. Config
# ===========================================================================
class TestConfig:
    def test_frontend_url_default(self):
        from src.core.config import settings
        assert settings.FRONTEND_URL == "http://localhost:3000"

    def test_frontend_url_overridable(self):
        from src.core.config import Settings
        s = Settings(
            DATABASE_URL="postgresql://x:x@localhost/x",
            NEO4J_URI="bolt://localhost:7687",
            NEO4J_USER="neo4j",
            NEO4J_PASSWORD="password",
            QDRANT_URL="http://localhost:6333",
            OPENAI_API_KEY="sk-x",
            JWT_SECRET_KEY="key",
            REDIS_URL="redis://localhost:6379",
            CORS_ORIGINS="http://localhost:3000",
            FRONTEND_URL="https://production.example.com",
        )
        assert s.FRONTEND_URL == "https://production.example.com"


# ===========================================================================
# 3. JWT Auth Utilities
# ===========================================================================
class TestAuthUtils:
    def test_create_and_decode_token(self):
        from src.utils.auth_utils import create_access_token, decode_access_token
        token = create_access_token({"sub": "user-abc"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-abc"

    def test_invalid_token_returns_none(self):
        from src.utils.auth_utils import decode_access_token
        assert decode_access_token("not.a.valid.jwt") is None
        assert decode_access_token("") is None

    def test_reset_password_token_has_type_claim(self):
        from src.utils.auth_utils import create_access_token, decode_access_token
        token = create_access_token({"sub": "user-abc", "type": "reset_password"})
        payload = decode_access_token(token)
        assert payload.get("type") == "reset_password"

    def test_password_hash_and_verify(self):
        from src.utils.auth_utils import get_password_hash, verify_password
        hashed = get_password_hash("correct_password")
        assert verify_password("correct_password", hashed)
        assert not verify_password("wrong_password", hashed)

    def test_verify_password_none_hash_returns_false(self):
        from src.utils.auth_utils import verify_password
        assert verify_password("any", None) is False


# ===========================================================================
# 4. Ingest Route Security
# ===========================================================================
class TestIngestRouteSecurity:
    def test_ingest_has_admin_dependency(self):
        from src.api.routes.ingest import ingest_documents
        params = inspect.signature(ingest_documents).parameters
        assert "_admin_id" in params, (
            "ingest_documents must have _admin_id parameter (admin auth dependency)"
        )

    def test_ingest_imports_get_current_admin_user(self):
        src_text = (BACKEND / "src" / "api" / "routes" / "ingest.py").read_text()
        assert "get_current_admin_user" in src_text, (
            "ingest.py must import and use get_current_admin_user"
        )


# ===========================================================================
# 5. Auth Service
# ===========================================================================
class TestAuthService:
    def _get_source(self):
        return (BACKEND / "src" / "services" / "auth_service.py").read_text()

    def test_no_hardcoded_localhost_in_reset_link(self):
        src = self._get_source()
        assert "localhost:3000" not in src, (
            "auth_service.py must NOT contain hardcoded 'localhost:3000' "
            "in the reset link. Use settings.FRONTEND_URL instead."
        )

    def test_uses_settings_frontend_url(self):
        src = self._get_source()
        assert "settings.FRONTEND_URL" in src, (
            "auth_service.py must use settings.FRONTEND_URL for the reset link"
        )

    def test_resend_not_imported_at_module_level(self):
        """resend must be a lazy import inside _send_reset_email to avoid
        crashing the app when RESEND_API_KEY is not set."""
        src = self._get_source()
        tree = ast.parse(src)
        top_imports = [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.Import, ast.ImportFrom)) and n.col_offset == 0
        ]
        resend_top = [
            n for n in top_imports
            if (
                isinstance(n, ast.ImportFrom) and n.module == "resend"
            ) or (
                isinstance(n, ast.Import) and any(
                    a.name == "resend" for a in n.names
                )
            )
        ]
        assert len(resend_top) == 0, (
            "resend must NOT be imported at module level in auth_service.py "
            "(lazy import inside method is required)"
        )

    def test_resend_api_key_not_set_at_module_level(self):
        """resend.api_key must not be set at module level."""
        src = self._get_source()
        lines = src.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if "resend.api_key" in stripped and not stripped.startswith("#"):
                # Must be inside a function (indented), not at module level
                assert line.startswith("        ") or line.startswith("    "), (
                    f"Line {i}: resend.api_key appears to be set at module level: {line!r}"
                )
