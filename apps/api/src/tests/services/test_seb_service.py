import hashlib
import plistlib

from src.services.courses.activities import seb


class _FakeRequest:
    """Minimal stand-in for fastapi.Request — only .headers.get is used."""

    def __init__(self, headers: dict):
        self.headers = headers


def test_is_seb_user_agent_accepts_seb_client():
    request = _FakeRequest({"user-agent": "Mozilla/5.0 SEB/3.6.2 (SEB_WIN)"})
    assert seb.is_seb_user_agent(request) is True


def test_is_seb_user_agent_rejects_regular_browser():
    request = _FakeRequest(
        {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"}
    )
    assert seb.is_seb_user_agent(request) is False


def test_is_seb_user_agent_rejects_missing_header():
    request = _FakeRequest({})
    assert seb.is_seb_user_agent(request) is False


def test_is_seb_user_agent_is_case_insensitive():
    request = _FakeRequest({"user-agent": "some-client seb/1.0 (SEB_MAC)"})
    assert seb.is_seb_user_agent(request) is True


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


def test_compute_config_key_hash_strips_url_fragment():
    with_fragment = seb.compute_config_key_hash("https://example.com/exam#section", "key123")
    without_fragment = seb.compute_config_key_hash("https://example.com/exam", "key123")
    assert with_fragment == without_fragment


def test_capture_seb_headers_reads_all_seb_related_headers():
    request = _FakeRequest(
        {
            seb.SEB_CONFIG_KEY_HEADER: "abc123",
            seb.SEB_LEGACY_REQUEST_HASH_HEADER: "def456",
            "user-agent": "SEB/3.6.2",
        }
    )
    captured = seb.capture_seb_headers(request)
    assert captured == {
        "config_key_hash": "abc123",
        "legacy_request_hash": "def456",
        "user_agent": "SEB/3.6.2",
    }


def test_capture_seb_headers_missing_headers_are_none():
    request = _FakeRequest({})
    captured = seb.capture_seb_headers(request)
    assert captured == {
        "config_key_hash": None,
        "legacy_request_hash": None,
        "user_agent": None,
    }


def test_hash_quit_password_matches_plain_sha256():
    assert seb.hash_quit_password("hunter2") == hashlib.sha256(b"hunter2").hexdigest()


def test_build_seb_config_plist_without_quit_password():
    raw = seb.build_seb_config_plist(
        exam_url="https://example.com/orgs/acme/course/1/activity/2",
        quit_url="https://example.com/seb-exit",
    )
    parsed = plistlib.loads(raw)

    assert parsed["startURL"] == "https://example.com/orgs/acme/course/1/activity/2"
    assert parsed["quitURL"] == "https://example.com/seb-exit"
    assert parsed["allowQuit"] is False
    assert parsed["quitURLConfirm"] is False
    assert parsed["sendBrowserExamKey"] is True
    assert "browserExamKey" not in parsed  # not a real SEB field, must not appear
    assert "hashedQuitPassword" not in parsed


def test_build_seb_config_plist_with_quit_password_is_hashed_not_plaintext():
    raw = seb.build_seb_config_plist(
        exam_url="https://example.com/exam",
        quit_url="https://example.com/seb-exit",
        quit_password="hunter2",
    )
    parsed = plistlib.loads(raw)

    assert parsed["hashedQuitPassword"] == hashlib.sha256(b"hunter2").hexdigest()
    assert "hunter2" not in raw.decode("utf-8", errors="ignore")
