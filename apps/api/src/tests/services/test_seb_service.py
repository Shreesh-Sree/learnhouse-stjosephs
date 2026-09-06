import hashlib
import plistlib

from src.services.courses.activities import seb


class _FakeRequest:
    """Minimal stand-in for fastapi.Request — only .headers.get is used."""

    def __init__(self, headers: dict):
        self.headers = headers


def test_generate_seb_config_key_is_random_and_long_enough():
    a = seb.generate_seb_config_key()
    b = seb.generate_seb_config_key()
    assert a != b
    assert len(a) == 64  # secrets.token_hex(32) -> 64 hex chars
    int(a, 16)  # valid hex


def test_compute_config_key_hash_is_deterministic():
    h1 = seb.compute_config_key_hash("https://example.com/exam", "key123")
    h2 = seb.compute_config_key_hash("https://example.com/exam", "key123")
    assert h1 == h2
    assert len(h1) == 64


def test_compute_config_key_hash_changes_with_url_or_key():
    base = seb.compute_config_key_hash("https://example.com/exam", "key123")
    assert base != seb.compute_config_key_hash("https://example.com/other", "key123")
    assert base != seb.compute_config_key_hash("https://example.com/exam", "key456")


def test_verify_seb_headers_accepts_matching_hash():
    url = "https://example.com/orgs/acme/course/1/activity/2"
    key = "secret-config-key"
    expected = seb.compute_config_key_hash(url, key)
    request = _FakeRequest({seb.SEB_CONFIG_KEY_HEADER: expected})
    assert seb.verify_seb_headers(request, key, url) is True


def test_verify_seb_headers_rejects_missing_header():
    request = _FakeRequest({})
    assert seb.verify_seb_headers(request, "key", "https://example.com") is False


def test_verify_seb_headers_rejects_wrong_hash():
    url = "https://example.com/exam"
    key = "secret-config-key"
    request = _FakeRequest({seb.SEB_CONFIG_KEY_HEADER: "0" * 64})
    assert seb.verify_seb_headers(request, key, url) is False


def test_verify_seb_headers_rejects_hash_computed_with_wrong_key():
    url = "https://example.com/exam"
    wrong_hash = seb.compute_config_key_hash(url, "a-different-key")
    request = _FakeRequest({seb.SEB_CONFIG_KEY_HEADER: wrong_hash})
    assert seb.verify_seb_headers(request, "secret-config-key", url) is False


def test_hash_quit_password_matches_plain_sha256():
    assert seb.hash_quit_password("hunter2") == hashlib.sha256(b"hunter2").hexdigest()


def test_build_seb_config_plist_without_quit_password():
    raw = seb.build_seb_config_plist(
        exam_url="https://example.com/orgs/acme/course/1/activity/2",
        config_key="the-config-key",
        quit_url="https://example.com/seb-exit",
    )
    parsed = plistlib.loads(raw)

    assert parsed["startURL"] == "https://example.com/orgs/acme/course/1/activity/2"
    assert parsed["browserExamKey"] == "the-config-key"
    assert parsed["quitURL"] == "https://example.com/seb-exit"
    assert parsed["allowQuit"] is False
    assert parsed["quitURLConfirm"] is False
    assert parsed["sendBrowserExamKey"] is True
    assert "hashedQuitPassword" not in parsed


def test_build_seb_config_plist_with_quit_password_is_hashed_not_plaintext():
    raw = seb.build_seb_config_plist(
        exam_url="https://example.com/exam",
        config_key="the-config-key",
        quit_url="https://example.com/seb-exit",
        quit_password="hunter2",
    )
    parsed = plistlib.loads(raw)

    assert parsed["hashedQuitPassword"] == hashlib.sha256(b"hunter2").hexdigest()
    assert "hunter2" not in raw.decode("utf-8", errors="ignore")
