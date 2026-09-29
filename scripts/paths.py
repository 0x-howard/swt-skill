"""Canonical paths for the source plugin package and its data layers."""

from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SHARED_ROOT = PLUGIN_ROOT / "shared"
SKILLS_ROOT = PLUGIN_ROOT / "skills"
REFERENCES_ROOT = PLUGIN_ROOT / "references"
RUNTIME_ROOT = REFERENCES_ROOT / "shared-runtime"
ASSETS_ROOT = PLUGIN_ROOT / "assets"
TESTS_ROOT = PLUGIN_ROOT / "tests"
DEFAULT_ASSUMPTIONS_PATH = REFERENCES_ROOT / "default-assumptions.json"
