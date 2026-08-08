"""
AuthService Unit Tests
=======================
Tests all business logic in AuthService using a mocked AsyncSession.
No real database connections are made.

Coverage:
  - register(): success, duplicate email
  - login(): success, wrong password, user not found
  - google_auth(): new user created, existing user returned
  - forgot_password(): user not found (generic), google user, normal user + email
  - reset_password(): valid token, invalid token, wrong type, user not found
  - _send_reset_email(): skipped when no API key, called when key present
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
BACKEND = pathlib.Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(
    email: str = "test@example.com",
    password_hash: str | None = "$2b$12$fakehash",
    is_google_login: bool = False,
    is_admin: bool = False,
    uid: str | None = None,
) -> MagicMock:
    """Return a mock User ORM object."""
    u = MagicMock()
    u.id = uid or str(uuid.uuid4())
    u.email = email
    u.password_hash = password_hash
    u.is_google_login = is_google_login
    u.is_admin = is_admin
    u.created_at = datetime.now(timezone.utc)
    return u


def _make_db(query_result=None) -> AsyncMock:
    """Return a mock AsyncSession.

    query_result: the object returned by result.scalars().first()
    """
    db = AsyncMock()
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = query_result
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    db.execute = AsyncMock(return_value=result_mock)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _run(coro):
    return asyncio.run(coro)


# ===========================================================================
# register()
# ===========================================================================
class TestRegister:
    def test_register_new_user_returns_token(self):
        from src.services.auth_service import AuthService
        from fastapi import HTTPException

        db = _make_db(query_result=None)  # no existing user

        async def mock_refresh(user):
            user.id = "new-user-id"

        db.refresh = mock_refresh

        with patch("src.services.auth_service.get_password_hash", return_value="hashed"):
            svc = AuthService(db)
            result = _run(svc.register("new@example.com", "password123"))

        assert "access_token" in result
        assert result["token_type"] == "bearer"
        assert result["user"]["email"] == "new@example.com"

    def test_register_duplicate_email_raises_400(self):
        from src.services.auth_service import AuthService
        from fastapi import HTTPException

        existing = _make_user(email="dup@example.com")
        db = _make_db(query_result=existing)
        svc = AuthService(db)

        with pytest.raises(HTTPException) as exc_info:
            _run(svc.register("dup@example.com", "pass"))

        assert exc_info.value.status_code == 400
        assert "already registered" in exc_info.value.detail.lower()

    def test_register_hashes_password(self):
        from src.services.auth_service import AuthService

        db = _make_db(query_result=None)
        db.refresh = AsyncMock()

        with patch("src.services.auth_service.get_password_hash", return_value="hashed_pw") as mock_hash:
            svc = AuthService(db)
            _run(svc.register("a@example.com", "mypassword"))
            mock_hash.assert_called_once_with("mypassword")


# ===========================================================================
# login()
# ===========================================================================
class TestLogin:
    def test_login_success(self):
        from src.services.auth_service import AuthService

        user = _make_user(email="user@example.com")
        db = _make_db(query_result=user)

        with patch("src.services.auth_service.verify_password", return_value=True):
            svc = AuthService(db)
            result = _run(svc.login("user@example.com", "correct_pw"))

        assert "access_token" in result
        assert result["user"]["email"] == "user@example.com"

    def test_login_wrong_password_raises_400(self):
        from src.services.auth_service import AuthService
        from fastapi import HTTPException

        user = _make_user()
        db = _make_db(query_result=user)

        with patch("src.services.auth_service.verify_password", return_value=False):
            svc = AuthService(db)
            with pytest.raises(HTTPException) as exc_info:
                _run(svc.login("user@example.com", "wrong"))

        assert exc_info.value.status_code == 400
        assert "incorrect" in exc_info.value.detail.lower()

    def test_login_user_not_found_raises_400(self):
        from src.services.auth_service import AuthService
        from fastapi import HTTPException

        db = _make_db(query_result=None)
        svc = AuthService(db)

        with pytest.raises(HTTPException) as exc_info:
            _run(svc.login("notexist@example.com", "any"))

        assert exc_info.value.status_code == 400

    def test_login_returns_bearer_type(self):
        from src.services.auth_service import AuthService

        user = _make_user()
        db = _make_db(query_result=user)

        with patch("src.services.auth_service.verify_password", return_value=True):
            svc = AuthService(db)
            result = _run(svc.login("user@example.com", "pw"))

        assert result["token_type"] == "bearer"


# ===========================================================================
# google_auth()
# ===========================================================================
class TestGoogleAuth:
    def _mock_google_verify(self, email: str):
        return patch(
            "src.services.auth_service.id_token.verify_oauth2_token",
            return_value={"email": email},
        )

    def test_google_auth_new_user_created(self):
        from src.services.auth_service import AuthService

        db = _make_db(query_result=None)
        created_user = _make_user(email="google@example.com", is_google_login=True)
        db.refresh = AsyncMock(side_effect=lambda u: setattr(u, "id", "google-id") or None)

        with self._mock_google_verify("google@example.com"):
            svc = AuthService(db)
            result = _run(svc.google_auth("fake-google-token"))

        db.add.assert_called_once()
        db.commit.assert_awaited()
        assert "access_token" in result

    def test_google_auth_existing_user_not_duplicated(self):
        from src.services.auth_service import AuthService

        existing = _make_user(email="existing@example.com", is_google_login=True)
        db = _make_db(query_result=existing)

        with self._mock_google_verify("existing@example.com"):
            svc = AuthService(db)
            result = _run(svc.google_auth("fake-token"))

        db.add.assert_not_called()
        assert result["user"]["email"] == "existing@example.com"

    def test_google_auth_invalid_token_raises_400(self):
        from src.services.auth_service import AuthService
        from fastapi import HTTPException

        db = _make_db(query_result=None)

        with patch(
            "src.services.auth_service.id_token.verify_oauth2_token",
            side_effect=ValueError("invalid token"),
        ):
            svc = AuthService(db)
            with pytest.raises(HTTPException) as exc_info:
                _run(svc.google_auth("bad-token"))

        assert exc_info.value.status_code == 400
        assert "invalid google token" in exc_info.value.detail.lower()

    def test_google_auth_missing_email_raises_400(self):
        from src.services.auth_service import AuthService
        from fastapi import HTTPException

        db = _make_db(query_result=None)

        with patch(
            "src.services.auth_service.id_token.verify_oauth2_token",
            return_value={"email": None},
        ):
            svc = AuthService(db)
            with pytest.raises(HTTPException) as exc_info:
                _run(svc.google_auth("token"))

        assert exc_info.value.status_code == 400


# ===========================================================================
# forgot_password()
# ===========================================================================
class TestForgotPassword:
    def test_user_not_found_returns_generic_message(self):
        from src.services.auth_service import AuthService

        db = _make_db(query_result=None)
        svc = AuthService(db)
        result = _run(svc.forgot_password("nobody@example.com"))

        assert "message" in result
        assert "if that email" in result["message"].lower()

    def test_google_login_user_raises_400(self):
        from src.services.auth_service import AuthService
        from fastapi import HTTPException

        user = _make_user(is_google_login=True)
        db = _make_db(query_result=user)
        svc = AuthService(db)

        with pytest.raises(HTTPException) as exc_info:
            _run(svc.forgot_password(user.email))

        assert exc_info.value.status_code == 400
        assert "google login" in exc_info.value.detail.lower()

    def test_normal_user_calls_send_email(self):
        from src.services.auth_service import AuthService

        user = _make_user(email="normal@example.com", is_google_login=False)
        db = _make_db(query_result=user)
        svc = AuthService(db)

        with patch.object(svc, "_send_reset_email") as mock_send:
            result = _run(svc.forgot_password(user.email))

        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        assert call_args[0] == user.email  # to_email
        assert "/reset-password?token=" in call_args[1]  # reset_link

    def test_reset_link_uses_frontend_url(self):
        from src.services.auth_service import AuthService
        from src.core.config import Settings

        user = _make_user(email="user@example.com", is_google_login=False)
        db = _make_db(query_result=user)
        svc = AuthService(db)

        captured_links = []

        def capture_send(to_email, reset_link):
            captured_links.append(reset_link)

        with patch.object(svc, "_send_reset_email", side_effect=capture_send):
            _run(svc.forgot_password(user.email))

        assert len(captured_links) == 1
        # Must start with FRONTEND_URL, not hardcoded localhost
        from src.core.config import settings
        assert captured_links[0].startswith(settings.FRONTEND_URL)
        assert "localhost:3000" not in captured_links[0].replace(settings.FRONTEND_URL, "")


# ===========================================================================
# reset_password()
# ===========================================================================
class TestResetPassword:
    def test_valid_token_updates_password(self):
        from src.services.auth_service import AuthService
        from src.utils.auth_utils import create_access_token

        user = _make_user(uid="user-123")
        db = _make_db(query_result=user)
        svc = AuthService(db)

        reset_token = create_access_token({"sub": "user-123", "type": "reset_password"})

        with patch("src.services.auth_service.get_password_hash", return_value="new_hash"):
            result = _run(svc.reset_password(reset_token, "new_password"))

        assert result["message"] == "Password updated successfully"
        assert user.password_hash == "new_hash"
        db.commit.assert_awaited()

    def test_invalid_token_raises_400(self):
        from src.services.auth_service import AuthService
        from fastapi import HTTPException

        db = _make_db()
        svc = AuthService(db)

        with pytest.raises(HTTPException) as exc_info:
            _run(svc.reset_password("not.a.valid.token", "newpass"))

        assert exc_info.value.status_code == 400
        assert "invalid" in exc_info.value.detail.lower()

    def test_wrong_token_type_raises_400(self):
        from src.services.auth_service import AuthService
        from src.utils.auth_utils import create_access_token
        from fastapi import HTTPException

        # Normal access token (no 'type' claim)
        normal_token = create_access_token({"sub": "user-123"})
        db = _make_db()
        svc = AuthService(db)

        with pytest.raises(HTTPException) as exc_info:
            _run(svc.reset_password(normal_token, "newpass"))

        assert exc_info.value.status_code == 400

    def test_user_not_found_raises_404(self):
        from src.services.auth_service import AuthService
        from src.utils.auth_utils import create_access_token
        from fastapi import HTTPException

        db = _make_db(query_result=None)  # no user found
        svc = AuthService(db)

        token = create_access_token({"sub": "ghost-user", "type": "reset_password"})

        with pytest.raises(HTTPException) as exc_info:
            _run(svc.reset_password(token, "newpass"))

        assert exc_info.value.status_code == 404


# ===========================================================================
# _send_reset_email()
# ===========================================================================
class TestSendResetEmail:
    def test_skipped_when_no_api_key(self):
        from src.services.auth_service import AuthService
        from src.core.config import Settings

        db = _make_db()
        svc = AuthService(db)

        with patch("src.core.config.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = None
            # Should not raise, just log a warning
            svc._send_reset_email("test@example.com", "http://example.com/reset?token=abc")

    def test_sends_when_api_key_present(self):
        from src.services.auth_service import AuthService

        db = _make_db()
        svc = AuthService(db)

        mock_resend = MagicMock()
        mock_resend.Emails.send = MagicMock()

        with (
            patch("src.core.config.settings") as mock_settings,
            patch.dict("sys.modules", {"resend": mock_resend}),
        ):
            mock_settings.RESEND_API_KEY = "re_test_key"
            svc._send_reset_email("user@example.com", "http://example.com/reset?token=abc")

        mock_resend.Emails.send.assert_called_once()
        call_kwargs = mock_resend.Emails.send.call_args[0][0]
        assert "user@example.com" in call_kwargs["to"]
        assert "reset" in call_kwargs["subject"].lower()

    def test_email_send_failure_does_not_raise(self):
        from src.services.auth_service import AuthService

        db = _make_db()
        svc = AuthService(db)

        mock_resend = MagicMock()
        mock_resend.Emails.send = MagicMock(side_effect=Exception("SMTP error"))

        with (
            patch("src.core.config.settings") as mock_settings,
            patch.dict("sys.modules", {"resend": mock_resend}),
        ):
            mock_settings.RESEND_API_KEY = "re_key"
            # Must NOT raise — failure is logged, not propagated
            svc._send_reset_email("user@example.com", "http://example.com/reset")
