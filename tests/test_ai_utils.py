"""Tests for AI assistant utilities — think-tag stripping, usage helpers."""
import pytest
from bot.handlers.ai_chat import _strip_think, _uses_left, FREE_USES
from db.models import UserUsage


class TestStripThink:
    def test_removes_think_block(self):
        text = "<think>internal reasoning</think>Final answer."
        assert _strip_think(text) == "Final answer."

    def test_removes_multiline_think(self):
        text = "<think>\nline1\nline2\n</think>Answer here."
        assert _strip_think(text) == "Answer here."

    def test_no_think_unchanged(self):
        text = "Just a normal response."
        assert _strip_think(text) == text

    def test_multiple_think_blocks(self):
        text = "<think>a</think>Result<think>b</think>."
        assert _strip_think(text) == "Result."

    def test_empty_think_block(self):
        text = "<think></think>Answer."
        assert _strip_think(text) == "Answer."

    def test_only_think_returns_empty(self):
        text = "<think>just thinking</think>"
        assert _strip_think(text) == ""

    def test_whitespace_stripped(self):
        text = "  <think>think</think>  answer  "
        result = _strip_think(text)
        assert result == "answer"


class TestUsesLeft:
    def test_free_only(self):
        u = UserUsage(telegram_id=1, free_uses_left=5, paid_uses=0)
        assert _uses_left(u) == 5

    def test_paid_only(self):
        u = UserUsage(telegram_id=1, free_uses_left=0, paid_uses=10)
        assert _uses_left(u) == 10

    def test_both(self):
        u = UserUsage(telegram_id=1, free_uses_left=3, paid_uses=7)
        assert _uses_left(u) == 10

    def test_zero(self):
        u = UserUsage(telegram_id=1, free_uses_left=0, paid_uses=0)
        assert _uses_left(u) == 0

    def test_free_uses_constant(self):
        assert FREE_USES == 5
