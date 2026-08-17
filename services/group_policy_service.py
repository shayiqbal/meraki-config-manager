"""Group Policy copy service — preview and execute cross-network policy copying.

Identity is based on policy *name* (case-insensitive).  A policy that already
exists on a destination (same name) is skipped; a policy whose name is absent
is created via POST.  No existing policies are ever overwritten.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from meraki_client.client_v1 import MerakiVpnClientV1


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass(slots=True)
class PolicyStatus:
    policy: dict[str, Any]
    status: Literal["new", "exists", "invalid"]
    detail: str = ""


@dataclass(slots=True)
class NetworkPolicyPreview:
    network_id: str
    network_name: str
    policy_statuses: list[PolicyStatus] = field(default_factory=list)

    @property
    def new_count(self) -> int:
        return sum(s.status == "new" for s in self.policy_statuses)

    @property
    def exists_count(self) -> int:
        return sum(s.status == "exists" for s in self.policy_statuses)

    @property
    def invalid_count(self) -> int:
        return sum(s.status == "invalid" for s in self.policy_statuses)

    @property
    def has_new_policies(self) -> bool:
        return self.new_count > 0


@dataclass(slots=True)
class PolicyCopyResult:
    network_id: str
    network_name: str
    success: bool
    policies_added: int = 0
    policies_skipped: int = 0
    error: str = ""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _name_key(policy: dict[str, Any]) -> str:
    """Normalised name used for identity comparison."""
    return (policy.get("name") or "").strip().lower()


def _summarise(policy: dict[str, Any]) -> str:
    """One-line human-readable summary of a policy's key settings."""
    parts: list[str] = []

    bw = policy.get("bandwidth", {})
    bw_setting = bw.get("settings", "network default")
    if bw_setting == "custom":
        limits = bw.get("bandwidthLimits", {})
        up   = limits.get("limitUp")
        down = limits.get("limitDown")
        up_s   = f"{up // 1000} Mbps"   if up   else "unlimited"
        down_s = f"{down // 1000} Mbps" if down else "unlimited"
        parts.append(f"bandwidth: {up_s} up / {down_s} down")
    else:
        parts.append(f"bandwidth: {bw_setting}")

    sched = policy.get("scheduling", {})
    parts.append("scheduling: enabled" if sched.get("enabled") else "scheduling: disabled")

    vlan = policy.get("vlanTagging", {})
    vlan_s = vlan.get("settings", "network default")
    if vlan_s == "custom":
        parts.append(f"VLAN: {vlan.get('vlanId', '?')}")
    else:
        parts.append(f"VLAN: {vlan_s}")

    fw = policy.get("firewallAndTrafficShaping", {})
    fw_s = fw.get("settings", "network default")
    if fw_s == "custom":
        l3 = len(fw.get("l3FirewallRules", []))
        l7 = len(fw.get("l7FirewallRules", []))
        ts = len(fw.get("trafficShapingRules", []))
        fw_detail = []
        if l3:
            fw_detail.append(f"{l3} L3")
        if l7:
            fw_detail.append(f"{l7} L7")
        if ts:
            fw_detail.append(f"{ts} shaping")
        parts.append("firewall: " + (", ".join(fw_detail) if fw_detail else "custom (empty)"))
    else:
        parts.append(f"firewall: {fw_s}")

    return "  |  ".join(parts)


# ── Service ────────────────────────────────────────────────────────────────────

class GroupPolicyCopyService:
    """Previews and executes copying selected group policies across networks."""

    def __init__(self, client: MerakiVpnClientV1) -> None:
        self.client = client

    # ── Preview ────────────────────────────────────────────────────────────────

    def preview(
        self,
        selected_policies: list[dict[str, Any]],
        destination_networks: list[dict[str, Any]],
    ) -> list[NetworkPolicyPreview]:
        """Return per-destination status for each selected policy (no changes made)."""
        previews: list[NetworkPolicyPreview] = []
        for network in destination_networks:
            existing = self.client.get_group_policies(network["id"])
            existing_names = {_name_key(p) for p in existing}
            statuses: list[PolicyStatus] = []
            for policy in selected_policies:
                try:
                    if not policy.get("name", "").strip():
                        statuses.append(PolicyStatus(
                            policy=policy,
                            status="invalid",
                            detail="Policy has no name — cannot be copied",
                        ))
                        continue
                    if _name_key(policy) in existing_names:
                        statuses.append(PolicyStatus(
                            policy=policy,
                            status="exists",
                            detail="Already present on this network — will be skipped",
                        ))
                    else:
                        statuses.append(PolicyStatus(
                            policy=policy,
                            status="new",
                            detail="Will be created",
                        ))
                except Exception as exc:
                    statuses.append(PolicyStatus(
                        policy=policy,
                        status="invalid",
                        detail=str(exc),
                    ))
            previews.append(NetworkPolicyPreview(
                network_id=network["id"],
                network_name=network["name"],
                policy_statuses=statuses,
            ))
        return previews

    # ── Execute ────────────────────────────────────────────────────────────────

    def execute(
        self,
        selected_policies: list[dict[str, Any]],
        destination_networks: list[dict[str, Any]],
        progress: Callable[[str], None] | None = None,
    ) -> list[PolicyCopyResult]:
        """Create new policies on each destination; skip those that already exist."""
        results: list[PolicyCopyResult] = []
        for network in destination_networks:
            if progress:
                progress(f"Copying to {network['name']}…")
            try:
                existing = self.client.get_group_policies(network["id"])
                existing_names = {_name_key(p) for p in existing}
                added = 0
                skipped = 0
                for policy in selected_policies:
                    if not policy.get("name", "").strip():
                        continue
                    if _name_key(policy) in existing_names:
                        skipped += 1
                        continue
                    self.client.create_group_policy(network["id"], policy)
                    added += 1
                results.append(PolicyCopyResult(
                    network_id=network["id"],
                    network_name=network["name"],
                    success=True,
                    policies_added=added,
                    policies_skipped=skipped,
                ))
            except Exception as exc:
                results.append(PolicyCopyResult(
                    network_id=network["id"],
                    network_name=network["name"],
                    success=False,
                    error=str(exc),
                ))
        return results


# ── Public helpers re-exported for use in the wizard ──────────────────────────
__all__ = [
    "PolicyStatus",
    "NetworkPolicyPreview",
    "PolicyCopyResult",
    "GroupPolicyCopyService",
    "_summarise",
]
