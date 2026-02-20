"""JSON export wrapper service."""


class JsonExportService:
    """Wrapper around SessionExporter with explicit data-layer naming."""

    def __init__(self, exporter):
        self.exporter = exporter

    def export_session(self, session_data):
        return self.exporter.export_session(session_data)

