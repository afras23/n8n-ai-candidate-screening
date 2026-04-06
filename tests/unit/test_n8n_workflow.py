"""
Unit tests for n8n workflow template JSON.
"""

from __future__ import annotations

import json
from pathlib import Path


def _workflow_payload() -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    workflow_path = root / "workflows" / "candidate_screening.json"
    payload = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_workflow_json_is_valid_json() -> None:
    payload = _workflow_payload()
    assert payload["name"]


def test_workflow_has_nodes_and_connections_keys() -> None:
    payload = _workflow_payload()
    assert "nodes" in payload
    assert "connections" in payload


def test_workflow_has_required_node_types() -> None:
    payload = _workflow_payload()
    nodes = payload.get("nodes")
    assert isinstance(nodes, list)
    node_types = {node.get("type") for node in nodes if isinstance(node, dict)}
    required = {
        "n8n-nodes-base.emailReadImap",
        "n8n-nodes-base.httpRequest",
        "n8n-nodes-base.switch",
        "n8n-nodes-base.googleSheets",
    }
    assert required.issubset(node_types)


def test_workflow_has_expected_chain_and_routing_graph() -> None:
    payload = _workflow_payload()
    nodes = payload.get("nodes")
    connections = payload.get("connections")
    assert isinstance(nodes, list)
    assert isinstance(connections, dict)

    nodes_by_name = {
        node.get("name"): node
        for node in nodes
        if isinstance(node, dict) and node.get("name")
    }

    # Expected chain in the exported template:
    # IF -> Extract Attachment -> HTTP Request -> Switch
    assert "IF — Has Attachment?" in nodes_by_name
    assert "Extract Attachment" in nodes_by_name
    assert "HTTP Request — Call Python API" in nodes_by_name
    assert "Switch — Route by Recommendation" in nodes_by_name

    if_main = connections.get("IF — Has Attachment?")
    assert isinstance(if_main, dict)
    if_edges = if_main.get("main")
    assert isinstance(if_edges, list)
    # index 0 (true) routes to Extract Attachment
    assert if_edges[0][0]["node"] == "Extract Attachment"

    extract_main = connections.get("Extract Attachment")
    assert isinstance(extract_main, dict)
    assert extract_main["main"][0][0]["node"] == "HTTP Request — Call Python API"

    http_main = connections.get("HTTP Request — Call Python API")
    assert isinstance(http_main, dict)
    assert http_main["main"][0][0]["node"] == "Switch — Route by Recommendation"

    # Switch must have exactly three explicit branches: shortlist, review, reject.
    switch_node = nodes_by_name["Switch — Route by Recommendation"]
    params = switch_node.get("parameters")
    assert isinstance(params, dict)
    rules = params.get("rules")
    assert isinstance(rules, list)
    rule_values = {rule.get("value") for rule in rules if isinstance(rule, dict)}
    assert rule_values == {"shortlist", "review", "reject"}

    # Limitation (intentional): the API may return `duplicate_skipped`, but the exported
    # workflow does not represent it as a routing branch.
    assert "duplicate_skipped" not in rule_values

    # Branch connections: each branch goes to an action node, then to Sheets logging.
    switch_main = connections.get("Switch — Route by Recommendation")
    assert isinstance(switch_main, dict)
    switch_edges = switch_main.get("main")
    assert isinstance(switch_edges, list)
    assert len(switch_edges) == 3
    assert switch_edges[0][0]["node"] == "HTTP Request — Update ATS (Shortlist)"
    assert switch_edges[1][0]["node"] == "HTTP Request — Flag for Review"
    assert switch_edges[2][0]["node"] == "Send Email — Rejection"

    assert (
        connections["HTTP Request — Update ATS (Shortlist)"]["main"][0][0]["node"]
        == "Google Sheets — Log Result"
    )
    assert (
        connections["HTTP Request — Flag for Review"]["main"][0][0]["node"]
        == "Google Sheets — Log Result"
    )
    assert (
        connections["Send Email — Rejection"]["main"][0][0]["node"]
        == "Google Sheets — Log Result"
    )
