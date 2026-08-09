from __future__ import annotations

import pytest

from rules.models import RuleCategory, RuleSet, VpnExclusionRule
from services.workflow import DriftDetected, WorkflowService


class FakeClient:
    def __init__(self, rules):
        self.rules = rules
        self.updated = []

    def get_rules(self, organization_id, network_id):
        return self.rules

    def update_rules(self, network_id, rules):
        self.updated.append((network_id, rules))
        return {"networkId": network_id}


def test_dry_run_and_deploy(existing):
    client = FakeClient(existing)
    service = WorkflowService(client)
    proposed = RuleSet(
        rules=[
            VpnExclusionRule(
                category=RuleCategory.CUSTOM,
                protocol="dns",
                destination="example.com",
            )
        ]
    )
    result = service.dry_run("o1", [{"id": "n1", "name": "Test"}], proposed)[0]
    assert result.change_count == 1
    assert service.deploy(result)["networkId"] == "n1"


def test_drift_blocks(existing):
    client = FakeClient(existing)
    service = WorkflowService(client)
    result = service.dry_run("o1", [{"id": "n1", "name": "Test"}], RuleSet())[0]
    client.rules = RuleSet(
        rules=[
            VpnExclusionRule(
                category=RuleCategory.CUSTOM,
                destination="10.0.0.0/8",
            )
        ]
    )
    with pytest.raises(DriftDetected):
        service.deploy(result)


def test_partial_network_failures_are_isolated(existing):
    class PartialClient(FakeClient):
        def get_rules(self, organization_id, network_id):
            if network_id == "bad":
                raise RuntimeError("unavailable")
            return self.rules

    service = WorkflowService(PartialClient(existing))
    good = service.dry_run("o1", [{"id": "good", "name": "Good"}], RuleSet())
    assert len(good) == 1
    with pytest.raises(RuntimeError):
        service.dry_run("o1", [{"id": "bad", "name": "Bad"}], RuleSet())

