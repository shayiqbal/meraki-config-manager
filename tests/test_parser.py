from __future__ import annotations

import json

import pytest

from rules.models import RuleCategory
from rules.parser import ImportValidationError, parse_file, parse_json_data


def test_csv_parser(samples):
    rules = parse_file(samples / "sample_vpn_exclusions.csv")
    assert len(rules.rules) == 10
    assert sum(r.category == RuleCategory.CUSTOM for r in rules.rules) == 9


def test_json_parser(samples):
    rules = parse_file(samples / "sample_vpn_exclusions.json")
    assert len(rules.rules) == 11
    assert rules.metadata["networkName"] == "31-GHIL"


def test_xlsx_parser(samples):
    rules = parse_file(samples / "sample_vpn_exclusions.xlsx")
    assert len(rules.rules) == 10
    assert rules.rules[-1].application_id == "meraki:layer7/application/1208"


def test_text_json(tmp_path):
    path = tmp_path / "rules.txt"
    path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "category": "custom",
                        "protocol": "dns",
                        "destination": "example.com",
                        "port": "any",
                    }
                ]
            }
        )
    )
    assert parse_file(path).rules[0].destination == "example.com"


def test_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{bad")
    with pytest.raises(ImportValidationError, match="line 1"):
        parse_file(path)


def test_invalid_row_reports_number():
    with pytest.raises(ImportValidationError, match="row/rule 1"):
        parse_json_data([{"category": "custom"}], "fixture")
