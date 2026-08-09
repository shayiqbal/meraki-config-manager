"""Extended Meraki client with network creation and configuration cloning for V1."""
from __future__ import annotations

from typing import Any

from meraki_client.client import MerakiVpnClient
from meraki_client.exceptions import MerakiClientError


class MerakiVpnClientV1(MerakiVpnClient):
    """Extends the base client with network management operations.

    All base VPN-exclusion methods are inherited unchanged.
    """

    # ── Network management ─────────────────────────────────────────────────

    def get_network(self, network_id: str) -> dict[str, Any]:
        return self._call(
            lambda: self.dashboard.networks.getNetwork(network_id),
            "get network",
            network_id=network_id,
        )

    def create_network(
        self,
        organization_id: str,
        name: str,
        product_types: list[str],
        timezone: str = "America/Los_Angeles",
        notes: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "name": name.strip(),
            "productTypes": product_types,
            "timeZone": timezone,
        }
        if notes.strip():
            kwargs["notes"] = notes.strip()
        if tags:
            kwargs["tags"] = tags
        return self._call(
            lambda: self.dashboard.organizations.createOrganizationNetwork(
                organization_id, **kwargs
            ),
            "create network",
            organization_id=organization_id,
            name=name,
        )

    def update_network(self, network_id: str, **kwargs: Any) -> dict[str, Any]:
        return self._call(
            lambda: self.dashboard.networks.updateNetwork(network_id, **kwargs),
            "update network",
            network_id=network_id,
        )

    # ── Appliance static routes ────────────────────────────────────────────

    def get_appliance_static_routes(self, network_id: str) -> list[dict[str, Any]]:
        return self._call(
            lambda: self.dashboard.appliance.getNetworkApplianceStaticRoutes(network_id),
            "get static routes",
            network_id=network_id,
        )

    def create_appliance_static_route(
        self,
        network_id: str,
        name: str,
        subnet: str,
        gateway_ip: str,
    ) -> dict[str, Any]:
        return self._call(
            lambda: self.dashboard.appliance.createNetworkApplianceStaticRoute(
                network_id,
                name=name,
                subnet=subnet,
                gatewayIp=gateway_ip,
            ),
            "create static route",
            network_id=network_id,
        )

    # ── Appliance firewall rules ───────────────────────────────────────────

    def get_appliance_firewall_l3_rules(self, network_id: str) -> dict[str, Any]:
        try:
            return self._call(
                lambda: self.dashboard.appliance.getNetworkApplianceFirewallL3FirewallRules(
                    network_id
                ),
                "get L3 firewall rules",
                network_id=network_id,
            )
        except MerakiClientError:
            return {"rules": []}

    def update_appliance_firewall_l3_rules(
        self,
        network_id: str,
        rules: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._call(
            lambda: self.dashboard.appliance.updateNetworkApplianceFirewallL3FirewallRules(
                network_id, rules=rules
            ),
            "update L3 firewall rules",
            network_id=network_id,
        )

    def get_appliance_firewall_l7_rules(self, network_id: str) -> dict[str, Any]:
        try:
            return self._call(
                lambda: self.dashboard.appliance.getNetworkApplianceFirewallL7FirewallRules(
                    network_id
                ),
                "get L7 firewall rules",
                network_id=network_id,
            )
        except MerakiClientError:
            return {"rules": []}

    def update_appliance_firewall_l7_rules(
        self,
        network_id: str,
        rules: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._call(
            lambda: self.dashboard.appliance.updateNetworkApplianceFirewallL7FirewallRules(
                network_id, rules=rules
            ),
            "update L7 firewall rules",
            network_id=network_id,
        )

    def get_appliance_ssids(self, network_id: str) -> list[dict[str, Any]]:
        try:
            return self._call(
                lambda: self.dashboard.appliance.getNetworkApplianceSsids(network_id),
                "get appliance SSIDs",
                network_id=network_id,
            )
        except MerakiClientError:
            return []

    def update_appliance_ssid(
        self, network_id: str, number: int | str, **kwargs: Any
    ) -> dict[str, Any]:
        """Update a single MX SSID slot (name, enabled, authMode, etc.)."""
        return self._call(
            lambda: self.dashboard.appliance.updateNetworkApplianceSsid(
                network_id, str(number), **kwargs
            ),
            "update appliance SSID",
            network_id=network_id,
            number=number,
        )

    def get_appliance_settings(self, network_id: str) -> dict[str, Any]:
        try:
            return self._call(
                lambda: self.dashboard.appliance.getNetworkApplianceSettings(network_id),
                "get appliance settings",
                network_id=network_id,
            )
        except MerakiClientError:
            return {}

    def update_appliance_settings(
        self, network_id: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Update appliance settings (clientTrackingMethod, deploymentMode, etc.)."""
        return self._call(
            lambda: self.dashboard.appliance.updateNetworkApplianceSettings(
                network_id, **kwargs
            ),
            "update appliance settings",
            network_id=network_id,
        )
