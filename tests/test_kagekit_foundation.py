"""Regression tests for the foundation.

* the layout contract: an action row can sit outside every container
* the injection points: swapping Theme / Limits changes branding, wording, colour, caps
* the invariant: the package imports nothing but discord.py and the standard library
"""

import ast
import pathlib
import sys

import pytest
from discord import Colour
from discord import ui as dui

from kagekit import (
    DISCORD_CLASSIC,
    ComponentBuilder,
    EmbedBuilder,
    FeatureDisabledError,
    Labels,
    Limits,
    Theme,
)
from kagekit.tokens import DEFAULT_PALETTE

PKG_DIR = pathlib.Path(__file__).resolve().parents[1] / "kagekit"

# Components V2 component types
_ACTION_ROW = 1
_CONTAINER = 17
_TEXT_DISPLAY = 10


class TestLayoutContract:
    """Section switches go outside at the top; reload/back/close outside at the bottom."""

    def test_outer_action_row_sits_outside_containers(self):
        cb = ComponentBuilder()
        cb.outer_action_row().button("Pending").button("Done")
        cb.container(DEFAULT_PALETTE.brand).text("## Settings")
        cb.outer_action_row().button("Reload").button("Back").button("Close")

        payload = cb.build().to_components()
        assert [c["type"] for c in payload] == [_ACTION_ROW, _CONTAINER, _ACTION_ROW]
        assert len(payload[0]["components"]) == 2
        assert len(payload[2]["components"]) == 3

    def test_inner_action_row_stays_inside_the_card(self):
        cb = ComponentBuilder()
        cb.container(DEFAULT_PALETTE.brand).text("## Settings")
        cb.action_row().button("Change")

        payload = cb.build().to_components()
        assert [c["type"] for c in payload] == [_CONTAINER]
        assert any(c["type"] == _ACTION_ROW for c in payload[0]["components"])

    def test_container_after_outer_row_returns_to_card_scope(self):
        """After an outer row, container() puts everything back inside a card."""
        cb = ComponentBuilder()
        cb.outer_action_row().button("Tab")
        cb.container(DEFAULT_PALETTE.danger).text("## Danger zone").button("Delete")

        payload = cb.build().to_components()
        assert [c["type"] for c in payload] == [_ACTION_ROW, _CONTAINER]
        assert any(c["type"] == _ACTION_ROW for c in payload[1]["components"])

    def test_cards_are_separate_containers(self):
        cb = ComponentBuilder()
        cb.container(DEFAULT_PALETTE.brand).text("## Settings")
        cb.container(DEFAULT_PALETTE.danger).text("## Danger zone")

        payload = cb.build().to_components()
        assert [c["type"] for c in payload] == [_CONTAINER, _CONTAINER]
        assert payload[0]["accent_color"] == DEFAULT_PALETTE.brand
        assert payload[1]["accent_color"] == DEFAULT_PALETTE.danger


class TestThemeInjection:
    def test_default_theme_has_no_branding(self):
        """Out of the box there is no branding."""
        cb = ComponentBuilder()
        cb.container().text("body")
        payload = cb.build().to_components()
        texts = [c["content"] for c in payload[0]["components"] if c["type"] == _TEXT_DISPLAY]
        assert texts == ["body"]

    def test_injected_footer_is_appended_as_subtext(self):
        cb = ComponentBuilder(theme=Theme(footer="Made with example.com"))
        cb.container().text("body")
        payload = cb.build().to_components()
        last = payload[0]["components"][-1]
        assert last == {"type": _TEXT_DISPLAY, "content": "-# Made with example.com"}

    def test_footer_lands_in_the_last_card_not_the_bottom_row(self):
        cb = ComponentBuilder(theme=Theme(footer="brand"))
        cb.container().text("body")
        cb.outer_action_row().button("Close")
        payload = cb.build().to_components()
        assert [c["type"] for c in payload] == [_CONTAINER, _ACTION_ROW]
        assert payload[0]["components"][-1]["content"] == "-# brand"

    def test_palette_swap_changes_embed_template_colors(self):
        classic = Theme(palette=DISCORD_CLASSIC)
        assert EmbedBuilder(theme=classic).success("x")._color == Colour(DISCORD_CLASSIC.success)
        assert EmbedBuilder().success("x")._color == Colour(DEFAULT_PALETTE.success)

    def test_labels_are_injectable(self):
        theme = Theme(labels=Labels(success_title="Nice"))
        assert EmbedBuilder(theme=theme).success("x").get_title() == "Nice"


class TestLimitsInjection:
    def test_defaults_are_unlimited(self):
        b = EmbedBuilder()
        b.url("https://example.com")
        for i in range(30):
            b.add_field(f"f{i}", "v")
        assert b.build().footer.text is None

    def test_url_can_be_disabled(self):
        b = EmbedBuilder(limits=Limits(embed_url_enabled=False))
        with pytest.raises(FeatureDisabledError):
            b.url("https://example.com")

    def test_field_cap_uses_injected_label(self):
        theme = Theme(labels=Labels(field_limit="max {max}"))
        b = EmbedBuilder(limits=Limits(max_embed_fields=1), theme=theme)
        b.add_field("a", "1")
        with pytest.raises(Exception, match="max 1"):
            b.add_field("b", "2")

    def test_branding_only_when_not_hidden(self):
        theme = Theme(footer="brand")
        shown = EmbedBuilder(limits=Limits(hide_branding=False), theme=theme).build()
        hidden = EmbedBuilder(limits=Limits(hide_branding=True), theme=theme).build()
        assert shown.footer.text == "brand"
        assert hidden.footer.text is None


class TestOssInvariant:
    """The package imports nothing but discord.py and the standard library.

    That invariant is what lets the same code serve a host application and ship as a
    standalone package. Breaking it makes the split expensive again.
    """

    @pytest.mark.parametrize("path", sorted(PKG_DIR.glob("*.py")), ids=lambda p: p.name)
    def test_no_first_party_imports(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        allowed = set(sys.stdlib_module_names) | {"discord"}

        roots = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots += [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # relative imports stay inside the package
                    continue
                if node.module:
                    roots.append(node.module.split(".")[0])

        offenders = sorted({r for r in roots if r not in allowed})
        assert not offenders, f"{path.name} imports outside the package: {offenders}"
