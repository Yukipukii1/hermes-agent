"""Tests for gateway /branch session metadata."""

from unittest.mock import MagicMock

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource, build_session_key


def _make_event(text="/branch", user_id="12345", chat_id="67890"):
    source = SessionSource(
        platform=Platform.TELEGRAM,
        user_id=user_id,
        chat_id=chat_id,
        user_name="testuser",
    )
    return MessageEvent(text=text, source=source)


@pytest.mark.asyncio
async def test_branch_persists_gateway_user_id(tmp_path):
    """Branched gateway sessions must preserve the originating user_id."""
    from gateway.run import GatewayRunner
    from hermes_state import SessionDB

    db = SessionDB(db_path=tmp_path / "state.db")
    current_session_id = "current_session_001"
    db.create_session(current_session_id, "telegram", user_id="12345")
    db.append_message(current_session_id, role="user", content="hello")
    db.append_message(current_session_id, role="assistant", content="hi")

    event = _make_event(text="/branch Side Quest")
    session_key = build_session_key(event.source)

    runner = object.__new__(GatewayRunner)
    runner._session_db = db
    runner.config = {}
    runner.adapters = {}
    runner._voice_mode = {}
    runner._session_key_for_source = MagicMock(return_value=session_key)
    runner._evict_cached_agent = MagicMock()

    current_entry = MagicMock()
    current_entry.session_id = current_session_id
    current_entry.session_key = session_key

    switched_entry = MagicMock()
    switched_entry.session_id = "branched-session"

    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = current_entry
    runner.session_store.load_transcript.return_value = db.get_messages_as_conversation(
        current_session_id
    )
    runner.session_store.switch_session.return_value = switched_entry

    result = await runner._handle_branch_command(event)

    assert "Branched to" in result
    branch_session_id = runner.session_store.switch_session.call_args[0][1]
    branch_session = db.get_session(branch_session_id)
    assert branch_session["user_id"] == "12345"
    db.close()
