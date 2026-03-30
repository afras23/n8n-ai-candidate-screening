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
