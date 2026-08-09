from __future__ import annotations

import pytest
from pydantic import ValidationError

from rules.models import RuleCategory, RuleSource, VpnExclusionRule


def test_rule_normalization_equivalence():
    first = VpnExclusionRule(
        category=RuleCategory.CUSTOM,
        destination="192.168.1.1",
        port="0",
    )
    second = VpnExclusionRule(
        category=RuleCategory.CUSTOM,
        destination="192.168.1.1/32",
        port="any",
    )
    assert first.fingerprint() == second.fingerprint()


def test_dns_normalization():
    rule = VpnExclusionRule(
        category=RuleCategory.CUSTOM,
        protocol="DNS",
        destination="Meraki.COM.",
    )
    assert rule.normalized_dict()["destination"] == "meraki.com"


def test_source_cidr_and_vlan_are_mutually_exclusive():
    with pytest.raises(ValidationError, match="both"):
        RuleSource(cidr="10.0.0.0/8", vlanId="20")


def test_invalid_port_is_rejected_on_normalization():
    rule = VpnExclusionRule(
        category=RuleCategory.CUSTOM, destination="10.0.0.0/8", port="70000"
    )
    with pytest.raises(ValueError, match="outside"):
        rule.fingerprint()


def test_application_payload():
    rule = VpnExclusionRule(
        category=RuleCategory.APPLICATION,
        application_id="meraki:layer7/application/1208",
        name="Microsoft Teams",
    )
    assert rule.api_dict()["id"].endswith("/1208")

