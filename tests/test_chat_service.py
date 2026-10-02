from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.db.models import ChatMessage, ChatSession
from app.services.chat_service import ChatService, SESSION_TITLE_MAX_LEN


def _db_with_result(items):
    scalars = MagicMock()
    scalars.all.return_value = items
    scalars.first.return_value = items[0] if items else None
    result = MagicMock()
    result.scalars.return_value = scalars
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.delete = AsyncMock()
    return db


def test_get_sessions_passes_capped_pagination_to_query():
    db = _db_with_result([])
    sessions = asyncio.run(ChatService(db).get_sessions(limit=999, offset=5))
    assert sessions == []
    statement = db.execute.await_args.args[0]
    assert statement._limit_clause.value == 200
    assert statement._offset_clause.value == 5


def test_get_session_returns_matching_session():
    session = SimpleNamespace(id="session-1")
    db = _db_with_result([session])
    assert asyncio.run(ChatService(db).get_session("session-1")) is session


def test_create_session_has_anonymous_owner_and_truncated_title():
    db = _db_with_result([])
    question = "Q" * (SESSION_TITLE_MAX_LEN + 20)
    session_id = asyncio.run(ChatService(db).create_session(question))

    uuid.UUID(session_id)
    session = db.add.call_args.args[0]
    assert isinstance(session, ChatSession)
    assert session.user_id is None
    assert session.title == "Q" * SESSION_TITLE_MAX_LEN + "…"
    db.commit.assert_awaited_once()


def test_create_session_keeps_short_question_as_title():
    db = _db_with_result([])
    asyncio.run(ChatService(db).create_session("A short question"))
    assert db.add.call_args.args[0].title == "A short question"


def test_get_session_messages_returns_query_results():
    message = SimpleNamespace(content="Answer")
    db = _db_with_result([message])
    assert asyncio.run(ChatService(db).get_session_messages("session-1")) == [
        message
    ]


def test_save_message_persists_and_returns_message():
    db = _db_with_result([])
    message = asyncio.run(
        ChatService(db).save_message("session-1", "user", "Hello")
    )
    assert isinstance(message, ChatMessage)
    assert message.session_id == "session-1"
    assert message.role == "user"
    assert message.content == "Hello"
    db.add.assert_called_once_with(message)
    db.commit.assert_awaited_once()


def test_chat_session_user_id_is_nullable():
    assert ChatSession.__table__.columns["user_id"].nullable is True
    for name in ("created_at", "updated_at"):
        column = ChatSession.__table__.columns[name]
        assert column.type.timezone is True


def test_message_timestamp_is_timezone_aware():
    assert ChatMessage.__table__.columns["created_at"].type.timezone is True
