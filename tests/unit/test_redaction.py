"""Tests for URL credential redaction."""

from __future__ import annotations

from codebase_architect.shared.redaction import redact_url_credentials


def test_redacts_token_userinfo() -> None:
    assert (
        redact_url_credentials("https://ghp_secret@github.com/o/r.git")
        == "https://***@github.com/o/r.git"
    )


def test_redacts_user_and_password() -> None:
    assert (
        redact_url_credentials("https://user:s3cret@gitlab.com/o/r.git")
        == "https://***@gitlab.com/o/r.git"
    )


def test_redacts_inside_error_text() -> None:
    msg = "git clone failed for https://oauth2:tok@host/r.git:\nfatal: auth"
    out = redact_url_credentials(msg)
    assert "tok" not in out
    assert "https://***@host/r.git" in out


def test_leaves_plain_urls_and_scp_form_untouched() -> None:
    assert redact_url_credentials("https://github.com/o/r.git") == "https://github.com/o/r.git"
    # scp-like SSH (git@host:path) carries no secret and is left as-is.
    assert redact_url_credentials("git@github.com:o/r.git") == "git@github.com:o/r.git"
