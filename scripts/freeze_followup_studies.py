"""Capture the committed runtime, installed image and both deterministic input sets."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess

from ledgerdesk.gnucash_tasks import gnucash_manifest
from ledgerdesk.robustness_fixtures import variant_manifest

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output",
                        help="Directory for new contexts; existing freezes are never overwritten")
    args = parser.parse_args()
    destinations = {campaign: args.output_dir / f"{campaign}-freeze-context.json" for campaign in ("office", "gnucash")}
    for destination in destinations.values():
        if destination.exists() or destination.is_symlink():
            raise RuntimeError(f"Refusing to overwrite an existing freeze: {destination}")
    paths = sorted((ROOT / "ledgerdesk").glob("*.py")) + [ROOT / name for name in (
        "scripts/run_robustness_study.py", "scripts/freeze_followup_studies.py", "compose.yaml",
        "docker/Dockerfile", "docker/start-desktop.sh", "fixtures/seed.json", "pyproject.toml")]
    files = {}
    for path in paths:
        name = str(path.relative_to(ROOT))
        committed = subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=ROOT)
        if committed != path.read_bytes():
            raise RuntimeError(f"Commit the runtime before freezing: {name}")
        files[name] = hashlib.sha256(committed).hexdigest()
    image = subprocess.check_output(["docker", "image", "inspect", "ledgerdesk-demo:local", "--format", "{{.Id}}"], text=True).strip()
    versions = subprocess.check_output(["docker", "run", "--rm", "--network", "none", "--entrypoint", "dpkg-query", "ledgerdesk-demo:local", "-W", "gnucash", "libreoffice-core"], text=True).strip()
    base = {"source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "code_files": files, "image_id": image, "environment": {
                "host": platform.platform(), "python": platform.python_version(), "openai_sdk": importlib.metadata.version("openai"),
                "model": "gpt-6.1-terra", "reasoning_effort": "medium", "display": [1200, 900],
                "normal_geometry": "maximized", "changed_geometry": [120, 80, 920, 660],
                "installed_applications": versions, "guest": "Linux arm64/X11", "agent_tools": ["computer"],
                "network": "isolated", "operator_corrections": "none during measured attempts"}}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for campaign, manifest in (("office", variant_manifest()), ("gnucash", gnucash_manifest())):
        destination = destinations[campaign]
        with destination.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps({**base, "campaign": campaign, "fixtures": manifest}, indent=2) + "\n")
        print(destination)


if __name__ == "__main__":
    main()
