import os

import pytest

from ledgerdesk import __main__ as cli


def test_session_lock_refuses_competing_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    with cli.session_lock():
        with pytest.raises(RuntimeError, match="owns the desktop"):
            with cli.session_lock():
                pytest.fail("Two commands acquired the desktop")
    with cli.session_lock():
        pass


def test_env_is_not_executed_and_only_loads_supported_names(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("LEDGERDESK_UNEXPECTED", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY='local-test-value'\nOPENAI_MODEL=gpt-6.1-terra\nLEDGERDESK_UNEXPECTED=ignored\n")
    cli.load_env(env_file)
    assert os.environ["OPENAI_API_KEY"] == "local-test-value"
    assert os.environ["OPENAI_MODEL"] == "gpt-6.1-terra"
    assert "LEDGERDESK_UNEXPECTED" not in os.environ


def test_env_does_not_override_existing_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setenv("OPENAI_API_KEY", "existing-test-value")
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=replacement-test-value\n")
    cli.load_env(env_file)
    assert os.environ["OPENAI_API_KEY"] == "existing-test-value"
