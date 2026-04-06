"""Tests for permission decisions."""

import logging

import pytest

from illusion.config.settings import PathRuleConfig, PermissionSettings
from illusion.permissions import PermissionChecker, PermissionMode


def test_default_mode_allows_read_only():
    checker = PermissionChecker(PermissionSettings(mode=PermissionMode.DEFAULT))
    decision = checker.evaluate("read_file", is_read_only=True)
    assert decision.allowed is True
    assert decision.requires_confirmation is False


def test_default_mode_requires_confirmation_for_mutation():
    checker = PermissionChecker(PermissionSettings(mode=PermissionMode.DEFAULT))
    decision = checker.evaluate("write_file", is_read_only=False)
    assert decision.allowed is False
    assert decision.requires_confirmation is True


def test_plan_mode_blocks_mutating_tools():
    checker = PermissionChecker(PermissionSettings(mode=PermissionMode.PLAN))
    decision = checker.evaluate("bash", is_read_only=False)
    assert decision.allowed is False
    assert "plan mode" in decision.reason


def test_full_auto_allows_mutating_tools():
    checker = PermissionChecker(PermissionSettings(mode=PermissionMode.FULL_AUTO))
    decision = checker.evaluate("bash", is_read_only=False)
    assert decision.allowed is True


# --- path_rules parsing tests ---


def _settings_with_rules(*rules) -> PermissionSettings:
    """Build a PermissionSettings with the given path_rule objects bypassing validation."""
    return PermissionSettings.model_construct(
        mode=PermissionMode.FULL_AUTO,
        allowed_tools=[],
        denied_tools=[],
        denied_commands=[],
        path_rules=list(rules),
    )


@pytest.mark.parametrize(
    "bad_rule",
    [
        PathRuleConfig.model_construct(allow=False),                  # pattern attribute missing
        PathRuleConfig.model_construct(pattern="", allow=False),      # pattern empty string
        PathRuleConfig.model_construct(pattern="   ", allow=False),   # pattern whitespace-only
        PathRuleConfig.model_construct(pattern=42, allow=False),      # pattern non-string
        PathRuleConfig.model_construct(pattern=None, allow=False),    # pattern None
    ],
    ids=["missing", "empty", "whitespace-only", "non-string", "none"],
)
def test_invalid_pattern_rule_is_skipped_and_warns(bad_rule, caplog):
    """Rules with missing, empty, or non-string patterns are skipped with a warning."""
    settings = _settings_with_rules(bad_rule)
    with caplog.at_level(logging.WARNING, logger="illusion.permissions.checker"):
        checker = PermissionChecker(settings)

    assert checker._path_rules == []
    assert "Skipping path rule" in caplog.text


def test_valid_deny_rule_blocks_matching_path():
    """A valid deny rule prevents access to a matching file path."""
    rule = PathRuleConfig(pattern="/etc/*", allow=False)
    settings = _settings_with_rules(rule)
    checker = PermissionChecker(settings)

    decision = checker.evaluate("read_file", is_read_only=True, file_path="/etc/passwd")
    assert decision.allowed is False
    assert "/etc/passwd" in decision.reason


def test_valid_deny_rule_does_not_block_non_matching_path():
    """A deny rule does not affect paths that don't match the pattern."""
    rule = PathRuleConfig(pattern="/etc/*", allow=False)
    settings = _settings_with_rules(rule)
    checker = PermissionChecker(settings)

    decision = checker.evaluate("read_file", is_read_only=True, file_path="/home/user/file.txt")
    assert decision.allowed is True


def test_valid_allow_rule_is_added():
    """A rule with allow=True is accepted and stored without warnings."""
    rule = PathRuleConfig(pattern="/data/*", allow=True)
    settings = _settings_with_rules(rule)
    checker = PermissionChecker(settings)

    assert len(checker._path_rules) == 1
    assert checker._path_rules[0].pattern == "/data/*"
    assert checker._path_rules[0].allow is True


def test_pattern_with_surrounding_whitespace_is_stripped():
    """A pattern with leading/trailing whitespace is accepted with whitespace stripped."""
    rule = PathRuleConfig.model_construct(pattern="  /etc/*  ", allow=False)
    settings = _settings_with_rules(rule)
    checker = PermissionChecker(settings)

    assert len(checker._path_rules) == 1
    assert checker._path_rules[0].pattern == "/etc/*"

    decision = checker.evaluate("read_file", is_read_only=True, file_path="/etc/passwd")
    assert decision.allowed is False
