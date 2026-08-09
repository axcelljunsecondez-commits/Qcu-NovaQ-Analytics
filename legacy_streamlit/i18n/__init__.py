"""
i18n — Internationalization support for the Queueing Theory Dashboard.

Usage:
    from i18n import t
    t("app.title")  # returns translated string
"""

from __future__ import annotations

import json
import os
from typing import Any

import streamlit as st

_SUPPORTED_LANGUAGES = ["en", "tl"]
_DEFAULT_LANG = "en"

_locale_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend",
    "public",
    "locales",
)

_translations: dict[str, dict[str, str]] = {}


def _load_translations(lang: str) -> dict[str, str]:
    """Load translations for a given language code."""
    path = os.path.join(_locale_dir, lang, "translation.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def init_i18n() -> None:
    """Initialize i18n session state."""
    if "locale" not in st.session_state:
        st.session_state["locale"] = _DEFAULT_LANG
    global _translations
    if not _translations:
        for lang in _SUPPORTED_LANGUAGES:
            _translations[lang] = _load_translations(lang)


def set_locale(lang: str) -> None:
    """Switch the current language."""
    if lang in _SUPPORTED_LANGUAGES:
        st.session_state["locale"] = lang
        st.rerun()


def get_locale() -> str:
    """Get the current language code."""
    return st.session_state.get("locale", _DEFAULT_LANG)


def t(key: str, **kwargs: Any) -> str:
    """Translate a key using the current locale.

    Supports simple string interpolation with {key} syntax.
    """
    init_i18n()
    lang = get_locale()
    translation = _translations.get(lang, {}).get(key)
    if translation is None:
        translation = _translations.get(_DEFAULT_LANG, {}).get(key, key)
    if kwargs and translation:
        translation = translation.format(**kwargs)
    return translation


def language_selector() -> None:
    """Render a language selector in the sidebar."""
    init_i18n()
    current = get_locale()
    labels = {"en": "🇺🇸 English", "tl": "🇵🇭 Filipino"}
    selected = st.sidebar.selectbox(
        "Language",
        options=_SUPPORTED_LANGUAGES,
        format_func=lambda x: labels.get(x, x),
        index=_SUPPORTED_LANGUAGES.index(current) if current in _SUPPORTED_LANGUAGES else 0,
    )
    if selected != current:
        set_locale(selected)
