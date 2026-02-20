"""Live session store alias under the new data package."""

from persistence.live_session_store import LiveSessionStore as _LiveSessionStore


class LiveSessionStore(_LiveSessionStore):
    """Re-export existing live session store under new architecture path."""

