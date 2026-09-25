"""Read-only graph loading and deterministic shortest-path queries."""
from __future__ import annotations

import json
import os
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402


class GraphUnavailable(RuntimeError):
    """The graph artifact cannot be read or does not have a usable shape."""


@dataclass
class GraphData:
    path: Path
    directed: bool
    nodes: dict[str, dict[str, Any]]
    adjacency: dict[str, list[tuple[str, dict[str, Any]]]]


def _path_value(raw: str, vault: Path | None) -> str:
    value = str(raw or "").replace("\\", "/").strip()
    if not value:
        return ""
    path = Path(value)
    if path.is_absolute() and vault is not None:
        try:
            return path.resolve().relative_to(vault.resolve()).as_posix()
        except (OSError, ValueError):
            pass
    while value.startswith("./"):
        value = value[2:]
    return value.lstrip("/")


def _edge_value(edge: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": str(edge.get("source", "")),
        "target": str(edge.get("target", "")),
        "relation": str(edge.get("relation") or ""),
        "confidence": edge.get("confidence"),
        "confidence_score": edge.get("confidence_score"),
        "source_file": edge.get("source_file"),
        "source_location": edge.get("source_location"),
    }


def load_graph(path: Path, vault: Path | None = None) -> GraphData:
    """Load node-link JSON and build a sorted undirected/directed adjacency map."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GraphUnavailable(f"graph.json onleesbaar: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), list):
        raise GraphUnavailable("graph.json heeft geen nodes-list")
    nodes: dict[str, dict[str, Any]] = {}
    for raw in data["nodes"]:
        if not isinstance(raw, dict) or raw.get("id") is None:
            continue
        node_id = str(raw["id"])
        node = dict(raw)
        node["id"] = node_id
        node["source_file"] = _path_value(str(raw.get("source_file") or ""), vault)
        nodes[node_id] = node
    raw_links = data.get("links")
    if raw_links is None:
        raw_links = data.get("edges") or []
    if not isinstance(raw_links, list):
        raise GraphUnavailable("graph.json links zijn geen list")
    directed = bool(data.get("directed", False))
    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = {
        node_id: [] for node_id in nodes
    }
    for raw in raw_links:
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source", ""))
        target = str(raw.get("target", ""))
        if source not in nodes or target not in nodes or source == target:
            continue
        edge = _edge_value(raw)
        adjacency[source].append((target, edge))
        if not directed:
            reverse = dict(edge)
            reverse["source"], reverse["target"] = target, source
            adjacency[target].append((source, reverse))
    for node_id in adjacency:
        adjacency[node_id].sort(key=lambda item: (
            item[0], item[1].get("relation") or "",
            str(item[1].get("confidence_score") or ""), item[1].get("source_file") or "",
        ))
    return GraphData(path=path, directed=directed, nodes=nodes, adjacency=adjacency)


def _node_document(node: dict[str, Any]) -> str:
    return str(node.get("source_file") or "").replace("\\", "/")


def _resolve_endpoint(query: str, graph: GraphData, vault: Path | None) -> dict[str, Any]:
    value = str(query or "").strip()
    if not value:
        return {"status": "invalid", "node_ids": [], "reason": "empty endpoint"}
    if value in graph.nodes:
        ids = [value]
        return {"status": "ok", "node_ids": ids}
    wanted_path = _path_value(value, vault)
    ids = sorted(
        node_id for node_id, node in graph.nodes.items()
        if wanted_path and _node_document(node) == wanted_path
    )
    if ids:
        return {"status": "ok", "node_ids": ids}
    ids = sorted(
        node_id for node_id, node in graph.nodes.items()
        if str(node.get("label") or "") == value
        or str(node.get("norm_label") or "") == value
    )
    if len(ids) == 1:
        return {"status": "ok", "node_ids": ids}
    if len(ids) > 1:
        return {"status": "ambiguous", "node_ids": ids,
                "reason": f"label matches {len(ids)} nodes"}
    return {"status": "not_found", "node_ids": [],
            "reason": f"no node or document matches {value!r}"}


def _node_payload(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(node.get("id", "")),
        "label": str(node.get("label") or ""),
        "source_file": node.get("source_file") or None,
        "file_type": node.get("file_type"),
        "community": node.get("community"),
    }


def _endpoint_payload(query: str, ids: list[str], graph: GraphData) -> dict[str, Any]:
    documents = []
    for node_id in ids:
        document = _node_document(graph.nodes[node_id])
        if document and document not in documents:
            documents.append(document)
    return {"query": query, "node_ids": ids, "documents": documents}


def _reconstruct(parent: dict[str, str | None], parent_edge: dict[str, dict[str, Any] | None],
                 current: str) -> tuple[list[str], list[dict[str, Any]]]:
    nodes: list[str] = []
    edges: list[dict[str, Any]] = []
    while current is not None:
        nodes.append(current)
        edge = parent_edge.get(current)
        if edge is not None:
            edges.append(edge)
        current = parent[current]
    nodes.reverse()
    edges.reverse()
    return nodes, edges


def shortest_path(source: str, target: str, *, graph_path: Path | None = None,
                  vault: Path | None = None, max_hops: int = 8) -> dict[str, Any]:
    """Return a deterministic BFS path and the documents containing its nodes."""
    try:
        budget = int(max_hops)
    except (TypeError, ValueError):
        return {"status": "invalid", "reason": "max_hops must be an integer"}
    if budget < 0:
        return {"status": "invalid", "reason": "max_hops must be non-negative"}
    budget = min(budget, 64)
    root = Path(vault) if vault is not None else vault_root()
    path = Path(graph_path) if graph_path is not None else root / "graphify-out" / "graph.json"
    try:
        graph = load_graph(path, root)
    except GraphUnavailable as exc:
        return {"status": "unavailable", "reason": str(exc), "path": str(path)}
    source_state = _resolve_endpoint(source, graph, root)
    target_state = _resolve_endpoint(target, graph, root)
    if source_state["status"] != "ok":
        return {"status": source_state["status"], "endpoint": "source",
                "reason": source_state.get("reason", ""),
                "candidates": source_state.get("node_ids", [])}
    if target_state["status"] != "ok":
        return {"status": target_state["status"], "endpoint": "target",
                "reason": target_state.get("reason", ""),
                "candidates": target_state.get("node_ids", [])}
    source_ids = sorted(source_state["node_ids"])
    target_ids = set(target_state["node_ids"])
    common = sorted(set(source_ids) & target_ids)
    if common:
        node_ids = [common[0]]
        return {
            "status": "self",
            "source": _endpoint_payload(source, source_ids, graph),
            "target": _endpoint_payload(target, sorted(target_state["node_ids"]), graph),
            "hops": 0,
            "path": [_node_payload(graph.nodes[common[0]])],
            "edges": [],
            "documents": [d for d in [
                _node_document(graph.nodes[common[0]])] if d],
            "warnings": _warnings(path),
        }
    queue: deque[tuple[str, int]] = deque((node_id, 0) for node_id in source_ids)
    parent: dict[str, str | None] = {node_id: None for node_id in source_ids}
    parent_edge: dict[str, dict[str, Any] | None] = {node_id: None for node_id in source_ids}
    found: str | None = None
    exceeded = False
    while queue:
        current, depth = queue.popleft()
        if depth >= budget:
            exceeded = True
            continue
        for neighbor, edge in graph.adjacency.get(current, []):
            if neighbor in parent:
                continue
            parent[neighbor] = current
            parent_edge[neighbor] = edge
            next_depth = depth + 1
            if neighbor in target_ids:
                found = neighbor
                queue.clear()
                break
            if next_depth < budget:
                queue.append((neighbor, next_depth))
            else:
                exceeded = True
        if found is not None:
            break
    if found is None:
        status = "too_long" if exceeded else "no_path"
        return {
            "status": status,
            "source": _endpoint_payload(source, source_ids, graph),
            "target": _endpoint_payload(target, sorted(target_state["node_ids"]), graph),
            "hops": None,
            "path": [],
            "edges": [],
            "documents": [],
            "warnings": _warnings(path),
        }
    node_ids, edges = _reconstruct(parent, parent_edge, found)
    path_nodes = [_node_payload(graph.nodes[node_id]) for node_id in node_ids]
    documents: list[str] = []
    for node in path_nodes:
        document = node.get("source_file")
        if document and document not in documents:
            documents.append(str(document))
    return {
        "status": "ok",
        "source": _endpoint_payload(source, source_ids, graph),
        "target": _endpoint_payload(target, sorted(target_state["node_ids"]), graph),
        "hops": len(node_ids) - 1,
        "path": path_nodes,
        "edges": edges,
        "documents": documents,
        "warnings": _warnings(path),
    }


def _warnings(path: Path) -> list[str]:
    flag = path.parent / ".needs-rebuild"
    return ["graph.json has a .needs-rebuild flag"] if flag.is_file() and flag.stat().st_size else []


def find_shortest_path(graph_path: Path, source: str, target: str, *,
                       vault: Path | None = None, max_hops: int = 8) -> dict[str, Any]:
    return shortest_path(source, target, graph_path=graph_path, vault=vault,
                         max_hops=max_hops)
