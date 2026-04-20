"""Diagnostics provider contract."""

from app.models.diagnostics import OpenSearchDiagnostics


class DiagnosticsProvider:
    def collect(self) -> OpenSearchDiagnostics:
        raise NotImplementedError


class DisabledDiagnosticsProvider(DiagnosticsProvider):
    def collect(self) -> OpenSearchDiagnostics:
        return OpenSearchDiagnostics(errors=["diagnostics disabled"])
