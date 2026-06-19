# GREEN in Plan 03 (was Wave 0 RED in Plan 02)
"""Translation parity tests (HACS-03).

Loads translations/en.json + translations/pl.json, recursively collects every
key path into a set, and asserts the two sets are EXACTLY equal. Also asserts
each required config/options/service key path is present in both files.
"""

import json
from pathlib import Path

TRANSLATIONS_DIR = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "whereiput_inventory"
    / "translations"
)

REQUIRED_KEY_PATHS = {
    "config.step.user.title",
    "config.step.user.data.base_url",
    "config.step.user.data.token",
    "config.step.user.description",
    "config.error.invalid_auth",
    "config.error.cannot_connect",
    "config.error.invalid_url",
    "config.abort.already_configured",
    "options.step.init.title",
    "options.step.init.data.areas",
    "services.search.name",
    "services.search.description",
    "services.search.fields.q.name",
    "services.search.fields.q.description",
}


def _load(lang: str) -> dict:
    return json.loads((TRANSLATIONS_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def _key_paths(node, prefix: str = "") -> set:
    """Recursively collect dotted key paths down to leaf (string) values."""
    paths: set = set()
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            paths |= _key_paths(value, path)
        else:
            paths.add(path)
    return paths


def test_en_and_pl_files_exist_and_are_valid_json() -> None:
    en, pl = _load("en"), _load("pl")
    assert isinstance(en, dict) and isinstance(pl, dict)


def test_en_pl_key_paths_are_identical() -> None:
    en_paths = _key_paths(_load("en"))
    pl_paths = _key_paths(_load("pl"))
    assert en_paths == pl_paths, (
        f"only in en: {en_paths - pl_paths}; only in pl: {pl_paths - en_paths}"
    )


def test_required_key_paths_present_in_both() -> None:
    en_paths = _key_paths(_load("en"))
    pl_paths = _key_paths(_load("pl"))
    missing_en = REQUIRED_KEY_PATHS - en_paths
    missing_pl = REQUIRED_KEY_PATHS - pl_paths
    assert not missing_en, f"missing in en.json: {missing_en}"
    assert not missing_pl, f"missing in pl.json: {missing_pl}"


def test_en_pl_config_step_keys_match() -> None:
    en, pl = _load("en"), _load("pl")
    assert set(en["config"]["step"]["user"]["data"]) == set(
        pl["config"]["step"]["user"]["data"]
    )


def test_en_pl_options_step_keys_match() -> None:
    en, pl = _load("en"), _load("pl")
    assert set(en["options"]["step"]["init"]["data"]) == set(
        pl["options"]["step"]["init"]["data"]
    )


def test_en_pl_services_search_keys_match() -> None:
    en, pl = _load("en"), _load("pl")
    assert set(en["services"]["search"]) == set(pl["services"]["search"])
