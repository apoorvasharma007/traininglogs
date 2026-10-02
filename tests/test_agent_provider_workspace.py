"""AnthropicProvider sends `anthropic-workspace-id` only when ANTHROPIC_WORKSPACE_ID is set --
needed for keys not scoped to a workspace. No real API calls; reads the client's own headers."""
from __future__ import annotations

import pytest

from traininglogs.agent.providers import AnthropicProvider


def test_workspace_header_sent_when_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_test")
    provider = AnthropicProvider()
    assert provider._client.default_headers["anthropic-workspace-id"] == "wrkspc_test"


def test_no_workspace_header_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    provider = AnthropicProvider()
    assert "anthropic-workspace-id" not in provider._client.default_headers
