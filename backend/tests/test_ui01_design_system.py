"""UI-01 — design-system contract tests.

No JS test runner is introduced (that would add a whole toolchain for a static
showcase — against the project's minimal-complexity rule). Instead these assert
the *contract* of the framework-agnostic assets: required tokens, components,
accessibility hooks and asset links exist and are internally consistent. This
catches a deleted token, a broken asset reference or a dropped ARIA role in the
existing Python CI with zero new tooling.
"""

from pathlib import Path

import pytest

DS = Path(__file__).resolve().parents[2] / "frontend" / "design-system"


@pytest.fixture(scope="module")
def assets():
    return {p.name: p.read_text(encoding="utf-8") for p in DS.glob("*")}


def test_asset_files_exist(assets):
    for name in ("index.html", "tokens.css", "components.css", "mobile.css", "showcase.js"):
        assert name in assets, name


def test_index_links_all_assets(assets):
    html = assets["index.html"]
    for ref in ("tokens.css", "components.css", "mobile.css", "showcase.js"):
        assert ref in html, ref


def test_core_design_tokens_present(assets):
    css = assets["tokens.css"]
    for token in ("--c-brand-500", "--c-ink-900", "--c-focus", "--sp-4",
                  "--r-md", "--fs-body", "--tap-min"):
        assert token in css, token


def test_dark_theme_and_reduced_motion(assets):
    css = assets["tokens.css"]
    assert '[data-theme="dark"]' in css
    assert "prefers-reduced-motion" in css


def test_component_classes_present(assets):
    css = assets["components.css"]
    for cls in (".btn--primary", ".input", ".badge--verified", ".alert--danger",
                ".card", ".price-breakdown", ".tab", ".skeleton", ".overlay"):
        assert cls in css, cls


def test_accessibility_hooks_present(assets):
    html, css = assets["index.html"], assets["components.css"]
    assert ":focus-visible" in css
    assert 'role="tablist"' in html and 'aria-selected' in html
    assert 'aria-modal="true"' in html
    assert 'aria-live' in html
    assert "Skip to content" in html


def test_transparent_pricing_is_shown_not_hidden(assets):
    """UX principle: the service fee must be visible in the breakdown."""
    html = assets["index.html"]
    assert "service fee" in html.lower()
    assert "price-breakdown" in html


def test_showcase_makes_no_backend_calls(assets):
    """The showcase must not hit real endpoints (mock-only)."""
    js = assets["showcase.js"]
    assert "fetch(" not in js
    assert "XMLHttpRequest" not in js
    assert "/v1/" not in js


def test_analytics_taxonomy_events_are_emitted(assets):
    js = assets["showcase.js"]
    for event in ("search_started", "booking_started", "payment_started",
                  "favorite_added", "filter_applied"):
        assert event in js, event


def test_mobile_patterns_present(assets):
    css, html = assets["mobile.css"], assets["index.html"]
    assert ".m-bottomnav" in css and ".sheet" in css and ".m-sticky" in css
    assert "device__screen" in html
