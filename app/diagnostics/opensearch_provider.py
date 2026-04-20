"""OpenSearch diagnostics provider using lightweight HTTP calls."""

from __future__ import annotations

import base64
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

from app.config import Settings
from app.diagnostics.base import DiagnosticsProvider
from app.models.diagnostics import OpenSearchDiagnostics


class OpenSearchDiagnosticsProvider(DiagnosticsProvider):
    def __init__(self, settings: Settings):
        self.settings = settings

    def collect(self) -> OpenSearchDiagnostics:
        diagnostics = OpenSearchDiagnostics()
        if not self.settings.opensearch_endpoint:
            diagnostics.errors.append("OPENSEARCH_ENDPOINT is not configured")
            return diagnostics

        diagnostics.cluster_health = self._get_json("/_cluster/health") or {}
        diagnostics.nodes = self._get_table("/_cat/nodes", "name,ip,node.role,heap.max,heap.percent,cpu,load_1m,disk.used_percent")
        diagnostics.allocation = self._get_table("/_cat/allocation", "node,shards,disk.used,disk.avail,disk.percent")
        diagnostics.indices = self._get_table("/_cat/indices", "health,status,index,pri,rep,docs.count,pri.store.size,store.size")
        diagnostics.shards = self._get_table("/_cat/shards", "index,shard,prirep,state,store,node")
        diagnostics.search_stats = self._collect_search_stats()
        diagnostics.errors.extend(getattr(self, "_errors", []))
        return diagnostics

    def _get_json(self, path: str) -> dict | None:
        try:
            status, body = self._request(path)
            if status == 200:
                return json.loads(body)
        except Exception as exc:
            self._record_error(path, exc)
        return None

    def _get_table(self, path: str, columns: str) -> list[dict]:
        query = urllib.parse.urlencode({"format": "json", "h": columns, "bytes": "gb"})
        try:
            status, body = self._request(f"{path}?{query}")
            if status == 200:
                payload = json.loads(body)
                return payload if isinstance(payload, list) else []
        except Exception as exc:
            self._record_error(path, exc)
        return []

    def _collect_search_stats(self) -> dict:
        payload = self._get_json("/_nodes/stats/indices,thread_pool") or {}
        totals = {
            "query_total": 0,
            "query_time_in_millis": 0,
            "search_current": 0,
            "search_queue": 0,
            "search_rejected": 0,
            "search_active": 0,
            "nodes": [],
        }
        for node_id, node in payload.get("nodes", {}).items():
            search = node.get("indices", {}).get("search", {})
            thread_pool = node.get("thread_pool", {}).get("search", {})
            node_stats = {
                "node_id": node_id,
                "name": node.get("name", ""),
                "roles": node.get("roles", []),
                "query_total": int(search.get("query_total", 0) or 0),
                "query_time_in_millis": int(search.get("query_time_in_millis", 0) or 0),
                "search_current": int(search.get("query_current", 0) or 0),
                "search_queue": int(thread_pool.get("queue", 0) or 0),
                "search_rejected": int(thread_pool.get("rejected", 0) or 0),
                "search_active": int(thread_pool.get("active", 0) or 0),
            }
            totals["query_total"] += node_stats["query_total"]
            totals["query_time_in_millis"] += node_stats["query_time_in_millis"]
            totals["search_current"] += node_stats["search_current"]
            totals["search_queue"] += node_stats["search_queue"]
            totals["search_rejected"] += node_stats["search_rejected"]
            totals["search_active"] += node_stats["search_active"]
            totals["nodes"].append(node_stats)
        return totals

    def _request(self, path: str) -> tuple[int, str]:
        endpoint = self.settings.opensearch_endpoint.rstrip("/")
        url = f"{endpoint}{path}"
        req = urllib.request.Request(url)
        if self.settings.opensearch_username or self.settings.opensearch_password:
            token = base64.b64encode(
                f"{self.settings.opensearch_username}:{self.settings.opensearch_password}".encode()
            ).decode()
            req.add_header("Authorization", f"Basic {token}")
        context = None if self.settings.opensearch_verify_tls else ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=self.settings.opensearch_timeout_seconds, context=context) as resp:
            return resp.status, resp.read().decode(errors="replace")

    def _record_error(self, path: str, exc: Exception) -> None:
        if not hasattr(self, "_errors"):
            self._errors = []
        if isinstance(exc, urllib.error.HTTPError):
            self._errors.append(f"{path}: HTTP {exc.code}")
        else:
            self._errors.append(f"{path}: {type(exc).__name__}: {exc}")
