from __future__ import annotations

import json

from reporting.summary import DeploymentSummary, NetworkResult


def test_summary_exports(tmp_path):
    summary = DeploymentSummary("o1", "Org")
    summary.networks.extend(
        [
            NetworkResult("n1", "One", True, created=2),
            NetworkResult("n2", "Two", False, error="failed"),
        ]
    )
    summary.finish()
    json_path = tmp_path / "summary.json"
    csv_path = tmp_path / "summary.csv"
    summary.export_json(json_path)
    summary.export_csv(csv_path)
    assert json.loads(json_path.read_text())["totals"]["created"] == 2
    assert "network_id" in csv_path.read_text()

