"""Unit tests for bililive_danmaku.gateway.auth."""

from bililive_danmaku.gateway.auth import Authenticator


class TestAuthenticator:
    """``Authenticator`` validates tokens against the configured list."""

    def test_listed_token_authenticates(self) -> None:
        authenticator = Authenticator(["alpha", "beta"])

        assert authenticator.authenticate("alpha") is True
        assert authenticator.authenticate("beta") is True

    def test_unlisted_token_is_rejected(self) -> None:
        authenticator = Authenticator(["alpha"])

        assert authenticator.authenticate("omega") is False

    def test_empty_token_is_rejected(self) -> None:
        authenticator = Authenticator(["alpha"])

        assert authenticator.authenticate("") is False

    def test_token_list_is_frozen_at_construction(self) -> None:
        tokens = ["alpha"]
        authenticator = Authenticator(tokens)

        tokens.append("omega")

        assert authenticator.authenticate("omega") is False
