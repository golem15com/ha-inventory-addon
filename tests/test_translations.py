# Wave 0 RED — GREEN in Plan 03/04
"""RED stub: translation parity.

Loads translations/en.json + translations/pl.json and asserts both contain
identical key sets under config.step.user.data, options.step.init.data and
services.search. The files do not exist yet (Plan 03/04 adds them), so this
fails on a real missing artifact.
"""

import json
from pathlib import Path

import pytest

TRANSLATIONS_DIR = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "whereiput_inventory"
    / "translations"
)


def _load(lang: str) -> dict:
    return json.loads((TRANSLATIONS_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def _keys_at(data: dict, *path: str) -> set:
    node = data
    for key in path:
        node = node[key]
    return set(node.keys())


def test_en_pl_config_step_keys_match() -> None:
    en, pl = _load("en"), _load("pl")
    assert _keys_at(en, "config", "step", "user", "data") == _keys_at(
        pl, "config", "step", "user", "data"
    )


def test_en_pl_options_step_keys_match() -> None:
    en, pl = _load("en"), _load("pl")
    assert _keys_at(en, "options", "step", "init", "data") == _keys_at(
        pl, "options", "step", "init", "data"
    )


def test_en_pl_services_search_keys_match() -> None:
    en, pl = _load("en"), _load("pl")
    assert set(en["services"]["search"].keys()) == set(
        pl["services"]["search"].keys()
    )
