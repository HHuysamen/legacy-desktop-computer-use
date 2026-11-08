import json
from pathlib import Path
import sys

import pytest

from scripts import freeze_followup_studies as freeze


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "ROOT", tmp_path)
    names = ["ledgerdesk/runtime.py", "scripts/run_robustness_study.py", "scripts/freeze_followup_studies.py",
             "compose.yaml", "docker/Dockerfile", "docker/start-desktop.sh", "fixtures/seed.json", "pyproject.toml"]
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic committed source\n")
    calls = []

    def execute(arguments, **kwargs):
        calls.append(arguments)
        if arguments[:2] == ["git", "show"]:
            return (tmp_path / arguments[-1].removeprefix("HEAD:")).read_bytes()
        if arguments[:2] == ["git", "rev-parse"]:
            return "a" * 40
        if arguments[:3] == ["docker", "image", "inspect"]:
            return "sha256:" + "b" * 64
        if arguments[:2] == ["docker", "run"]:
            return "gnucash test-version\nlibreoffice test-version"
        raise AssertionError(arguments)

    monkeypatch.setattr(freeze.subprocess, "check_output", execute)
    monkeypatch.setattr(freeze.platform, "platform", lambda: "test-platform")
    monkeypatch.setattr(freeze.platform, "python_version", lambda: "3.test")
    monkeypatch.setattr(freeze.importlib.metadata, "version", lambda name: "test-sdk")
    monkeypatch.setattr(freeze, "variant_manifest", lambda: {"protocol": "office-fixture"})
    monkeypatch.setattr(freeze, "gnucash_manifest", lambda: {"protocol": "gnucash-fixture"})
    return tmp_path, calls


def test_new_output_directory_preserves_original_freezes(environment, monkeypatch):
    root, _ = environment
    original = root / "output"
    original.mkdir()
    for name in ("office", "gnucash"):
        (original / f"{name}-freeze-context.json").write_text(f"original {name}")
    target = root / "repair-freeze"
    monkeypatch.setattr(sys, "argv", ["freeze", "--output-dir", str(target)])
    freeze.main()
    for name in ("office", "gnucash"):
        assert (original / f"{name}-freeze-context.json").read_text() == f"original {name}"
        frozen = json.loads((target / f"{name}-freeze-context.json").read_text())
        assert frozen["campaign"] == name
        assert frozen["source_revision"] == "a" * 40
        assert frozen["image_id"] == "sha256:" + "b" * 64
        assert frozen["code_files"]


@pytest.mark.parametrize("existing", ["office", "gnucash"])
def test_all_destination_files_are_preflighted_before_any_write_or_probe(environment, monkeypatch, existing):
    root, calls = environment
    target = root / "existing"
    target.mkdir()
    prior = target / f"{existing}-freeze-context.json"
    prior.write_text("must remain unchanged")
    monkeypatch.setattr(sys, "argv", ["freeze", "--output-dir", str(target)])
    with pytest.raises(RuntimeError, match="overwrite"):
        freeze.main()
    assert calls == []
    assert prior.read_text() == "must remain unchanged"
    assert len(list(target.iterdir())) == 1


def test_dangling_destination_symlink_is_not_overwritten(environment, monkeypatch):
    root, calls = environment
    target = root / "existing"
    target.mkdir()
    pointer = target / "gnucash-freeze-context.json"
    pointer.symlink_to(root / "missing")
    monkeypatch.setattr(sys, "argv", ["freeze", "--output-dir", str(target)])
    with pytest.raises(RuntimeError, match="overwrite"):
        freeze.main()
    assert pointer.is_symlink()
    assert calls == []


def test_uncommitted_runtime_is_rejected_before_container_probes(environment, monkeypatch):
    root, calls = environment
    original = freeze.subprocess.check_output

    def changed(arguments, **kwargs):
        if arguments[:2] == ["git", "show"]:
            return b"different committed content"
        return original(arguments, **kwargs)

    monkeypatch.setattr(freeze.subprocess, "check_output", changed)
    target = root / "new"
    monkeypatch.setattr(sys, "argv", ["freeze", "--output-dir", str(target)])
    with pytest.raises(RuntimeError, match="Commit the runtime"):
        freeze.main()
    assert not target.exists()
    assert calls == []
