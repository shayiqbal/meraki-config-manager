from __future__ import annotations

from rules.comparer import compare
from rules.models import ChangeKind, RuleCategory, RuleSet, VpnExclusionRule


def test_identical_is_unchanged(existing, custom_rule):
    result = compare(existing, RuleSet(rules=[custom_rule]))
    assert result.count(ChangeKind.UNCHANGED) == 1
    assert len(result.final.rules) == 1


def test_duplicate_is_blocker(custom_rule):
    result = compare(RuleSet(), RuleSet(rules=[custom_rule, custom_rule.model_copy()]))
    assert result.count(ChangeKind.DUPLICATE) == 1
    assert result.has_blockers


def test_merge_preserves_unrelated(existing):
    new = VpnExclusionRule(
        category=RuleCategory.CUSTOM, protocol="dns", destination="example.com"
    )
    result = compare(existing, RuleSet(rules=[new]))
    assert result.count(ChangeKind.NEW) == 1
    assert len(result.final.rules) == 2


def test_replace_removes_unlisted(existing):
    result = compare(existing, RuleSet(rules=[], mode="replace"))
    assert result.count(ChangeKind.REMOVED) == 1
    assert not result.final.rules


def test_explicit_remove(existing, custom_rule):
    remove = custom_rule.model_copy(update={"action": "remove"})
    result = compare(existing, RuleSet(rules=[remove]))
    assert result.count(ChangeKind.REMOVED) == 1
    assert not result.final.rules

