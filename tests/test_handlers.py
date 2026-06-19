from __future__ import annotations

from types import SimpleNamespace

from app.bot.handlers import _build_ai_context, _is_active_bot_status, _is_ai_trigger


def test_is_ai_trigger_matches_bot_username():
    message = SimpleNamespace(
        text="Привет, @family_bot",
        caption=None,
        reply_to_message=None,
    )

    assert _is_ai_trigger(message, bot_username="family_bot", bot_user_id=None) is True


def test_is_ai_trigger_matches_reply_to_bot():
    message = SimpleNamespace(
        text="Ответ",
        caption=None,
        reply_to_message=SimpleNamespace(from_user=SimpleNamespace(id=42)),
    )

    assert _is_ai_trigger(message, bot_username=None, bot_user_id=42) is True


def test_build_ai_context_includes_author_and_message_text():
    message = SimpleNamespace(
        text="Как дела?",
        caption=None,
        from_user=SimpleNamespace(full_name="Andrei", username="andrei"),
    )

    context = _build_ai_context(message)

    assert "Andrei" in context
    assert "Как дела?" in context


def test_is_active_bot_status_matches_member_like_statuses():
    assert _is_active_bot_status("member") is True
    assert _is_active_bot_status("administrator") is True
    assert _is_active_bot_status("left") is False
    assert _is_active_bot_status("kicked") is False
