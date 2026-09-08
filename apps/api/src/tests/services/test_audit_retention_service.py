"""Tests for src/services/audit/retention.py.

The end-to-end purge (real row deletion against a real cutoff, real dry-run
vs. live behavior, org-scoped rows purged while org_id=NULL login/logout
rows are left untouched) was verified by hand against a live Postgres 16
database in this session (see PENDING_FEATURES.md) — inserting real rows at
known ages, running the real endpoint, and confirming exactly the expected
row was deleted and no others. This file covers the pure config-parsing
logic that doesn't need a database at all.
"""

from types import SimpleNamespace

import pytest

from src.services.audit.retention import (
    MIN_RETENTION_DAYS,
    get_retention_days,
    retention_scheduler_enabled,
)


class TestGetRetentionDays:
    def test_no_config_returns_none(self):
        assert get_retention_days(None) is None

    def test_empty_config_returns_none(self):
        assert get_retention_days(SimpleNamespace(config={})) is None

    def test_config_without_audit_key_returns_none(self):
        assert get_retention_days(SimpleNamespace(config={"active": True})) is None

    def test_valid_retention_days_returned(self):
        config = SimpleNamespace(config={"audit": {"retention_days": 90}})
        assert get_retention_days(config) == 90

    def test_zero_or_negative_treated_as_no_policy(self):
        assert get_retention_days(SimpleNamespace(config={"audit": {"retention_days": 0}})) is None
        assert get_retention_days(SimpleNamespace(config={"audit": {"retention_days": -5}})) is None

    def test_non_numeric_value_treated_as_no_policy(self):
        assert get_retention_days(SimpleNamespace(config={"audit": {"retention_days": "not a number"}})) is None

    def test_float_days_coerced_to_int(self):
        config = SimpleNamespace(config={"audit": {"retention_days": 45.0}})
        assert get_retention_days(config) == 45


class TestRetentionSchedulerEnabled:
    @pytest.mark.parametrize("value", ["1", "true", "True", "yes", "on"])
    def test_truthy_values_enable(self, monkeypatch, value):
        monkeypatch.setenv("LEARNHOUSE_AUDIT_RETENTION_ENABLED", value)
        assert retention_scheduler_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
    def test_falsy_values_disable(self, monkeypatch, value):
        monkeypatch.setenv("LEARNHOUSE_AUDIT_RETENTION_ENABLED", value)
        assert retention_scheduler_enabled() is False

    def test_unset_defaults_to_disabled(self, monkeypatch):
        monkeypatch.delenv("LEARNHOUSE_AUDIT_RETENTION_ENABLED", raising=False)
        assert retention_scheduler_enabled() is False


def test_minimum_retention_days_is_reasonable():
    # A sanity floor — the whole point is to keep a fat-fingered "5" from
    # nuking a month of audit history. This test exists so a future edit
    # weakening it has to do so on purpose.
    assert MIN_RETENTION_DAYS >= 30
