"""Tests for src.token_usage."""

import pytest

from src.token_usage import estimate_tokens


class TestEstimateTokens:
    @pytest.mark.parametrize("payload", [b"", "", None])
    def test_empty_payload_costs_nothing(self, payload: bytes | str | None) -> None:
        assert estimate_tokens(payload or b"") == 0

    def test_counts_four_characters_per_token(self) -> None:
        assert estimate_tokens("a" * 400) == 100

    def test_accepts_bytes_and_str_alike(self) -> None:
        assert estimate_tokens(b"a" * 400) == estimate_tokens("a" * 400)

    def test_shorter_than_one_token_rounds_down(self) -> None:
        assert estimate_tokens("abc") == 0

    def test_decodes_utf8_rather_than_counting_bytes(self) -> None:
        """Accented text must not be charged twice for its multi-byte encoding."""
        text = "ãçõéá" * 100  # 500 characters, 1000 bytes in UTF-8
        assert estimate_tokens(text.encode("utf-8")) == 125

    def test_invalid_utf8_does_not_raise(self) -> None:
        assert estimate_tokens(b"\xff\xfe" * 100) >= 0
