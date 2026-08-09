from __future__ import annotations

from pathlib import Path

import pytest

from rules.models import RuleCategory, RuleSet, VpnExclusionRule


@pytest.fixture
def custom_rule() -> VpnExclusionRule:
    return VpnExclusionRule(
        category=RuleCategory.CUSTOM,
        protocol="any",
        destination="192.168.1.1",
        port="any",
    )


@pytest.fixture
def existing(custom_rule) -> RuleSet:
    return RuleSet(rules=[custom_rule])


@pytest.fixture
def samples() -> Path:
    return Path(__file__).parents[1] / "samples"

