from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from config.settings import Settings
from meraki_client.client import MerakiVpnClient
from meraki_client.exceptions import CompatibilityError
from rules.models import RuleCategory, RuleSet, VpnExclusionRule


class Organizations:
    def getOrganizations(self):
        return [{"id": "o1", "name": "Org"}]

    def getOrganizationNetworks(self, organization_id, total_pages):
        return [
            {"id": "mx", "name": "MX", "productTypes": ["appliance"]},
            {"id": "mr", "name": "MR", "productTypes": ["wireless"]},
        ]


class Appliance:
    def __init__(self):
        self.updated = None

    def getOrganizationApplianceTrafficShapingVpnExclusionsByNetwork(
        self, organization_id, total_pages, networkIds
    ):
        return {
            "items": [
                {
                    "networkId": networkIds[0],
                    "networkName": "MX",
                    "custom": [
                        {
                            "protocol": "dns",
                            "destination": "meraki.com",
                            "port": "any",
                        }
                    ],
                    "majorApplications": [],
                    "applications": [],
                }
            ]
        }

    def updateNetworkApplianceTrafficShapingVpnExclusions(self, network_id, **kwargs):
        self.updated = kwargs
        return {"networkId": network_id, **kwargs}


class Dashboard:
    def __init__(self):
        self.organizations = Organizations()
        self.appliance = Appliance()


def client(early_access=True):
    return MerakiVpnClient(
        Settings(api_key="not-a-real-key", early_access=early_access),
        logging.getLogger("test"),
        dashboard=Dashboard(),
    )


def test_api_calls_are_wrapped_and_filtered():
    api = client()
    assert api.organizations()[0]["name"] == "Org"
    assert [item["id"] for item in api.networks("o1")] == ["mx"]
    rules = api.get_rules("o1", "mx")
    assert rules.rules[0].destination == "meraki.com"


def test_update_sends_only_vpn_exclusion_arrays():
    """When applications rules exist, update_rules should POST all three arrays
    via the direct HTTP path (bypassing the SDK which silently drops 'applications')."""
    api = client()
    rules = RuleSet(
        rules=[
            VpnExclusionRule(
                category=RuleCategory.APPLICATION,
                application_id="meraki:layer7/application/1208",
                name="Microsoft Teams",
            )
        ]
    )
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {}

    with patch("meraki_client.client._requests.put", return_value=mock_response) as mock_put:
        api.update_rules("mx", rules)
        assert mock_put.called
        _, kwargs = mock_put.call_args
        payload = kwargs.get("json", {})
        assert "custom" in payload
        assert "majorApplications" in payload
        assert "applications" in payload
        assert payload["applications"][0]["name"] == "Microsoft Teams"


def test_early_access_guard():
    api = client(early_access=False)
    rules = RuleSet(
        rules=[
            VpnExclusionRule(
                category=RuleCategory.APPLICATION,
                application_id="meraki:layer7/application/1208",
                name="Microsoft Teams",
            )
        ]
    )
    with pytest.raises(CompatibilityError, match="early-access"):
        api.update_rules("mx", rules)

