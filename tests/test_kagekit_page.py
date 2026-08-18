"""Regression tests for the declarative layer (Page / Card / TabBar / Pager / ActionBar).

They check that the layout contract is enforced by the structure rather than by
convention.
"""

import discord
import pytest

from kagekit import (
    Action,
    ActionBar,
    Actions,
    Card,
    Divider,
    LimitError,
    Page,
    Pager,
    Select,
    SettingRow,
    Tab,
    TabBar,
    Text,
)
from kagekit.page import JumpModal
from kagekit.tokens import DEFAULT_PALETTE

_ACTION_ROW = 1
_BUTTON = 2
_STRING_SELECT = 3
_CONTAINER = 17


async def noop(interaction, *args):  # handler stub
    return None


def build(page: Page):
    return page.build().to_components()


class TestPageOrder:
    def test_parts_land_in_contract_order(self):
        payload = build(
            Page(
                tabs=TabBar(tabs=[Tab("Pending", "pending")], on_change=noop),
                body=[Card(title="## A"), Card(title="## B")],
                pager=Pager(current=1, total=3, on_change=noop),
                actions=ActionBar(on_close=noop),
            )
        )
        assert [c["type"] for c in payload] == [
            _ACTION_ROW,  # TabBar    — outside, at the top
            _CONTAINER,  # Card
            _CONTAINER,  # Card
            _ACTION_ROW,  # Pager     — its own row
            _ACTION_ROW,  # ActionBar — outside, at the bottom
        ]

    def test_omitted_parts_take_no_slot(self):
        payload = build(Page(body=[Card(title="## A")]))
        assert [c["type"] for c in payload] == [_CONTAINER]

    def test_action_bar_without_handlers_is_not_rendered(self):
        payload = build(Page(body=[Card(title="## A")], actions=ActionBar()))
        assert [c["type"] for c in payload] == [_CONTAINER]


class TestCard:
    def test_intent_resolves_to_palette(self):
        payload = build(Page(body=[Card(title="## X", intent="danger")]))
        assert payload[0]["accent_color"] == DEFAULT_PALETTE.danger

    def test_unknown_intent_is_rejected(self):
        with pytest.raises(ValueError, match="unknown intent"):
            build(Page(body=[Card(title="## X", intent="scary")]))

    def test_explicit_accent_wins(self):
        payload = build(Page(body=[Card(title="## X", intent="brand", accent=0x123456)]))
        assert payload[0]["accent_color"] == 0x123456

    def test_text_after_a_setting_row_does_not_leak_into_it(self):
        """text() straight after a real section is swallowed by it — the known trap.

        The declarative layer closes the section first, so the note becomes its own
        TextDisplay.
        """
        payload = build(
            Page(
                body=[
                    Card(
                        children=[
                            SettingRow(
                                "Category", "Support", emoji="📂", action="Change", on_click=noop
                            ),
                            Divider(),
                            Text("note"),
                        ]
                    )
                ]
            )
        )
        children = payload[0]["components"]
        section = next(c for c in children if c["type"] == 9)
        assert len(section["components"]) == 1  # the setting row alone
        assert children[-1] == {"type": 10, "content": "note"}

    def test_setting_row_without_handler_is_disabled(self):
        payload = build(Page(body=[Card(children=[SettingRow("key", "value", action="Change")])]))
        section = next(c for c in payload[0]["components"] if c["type"] == 9)
        assert section["accessory"]["disabled"] is True


class TestCardActions:
    def test_actions_render_as_a_row_inside_the_card(self):
        payload = build(
            Page(
                body=[
                    Card(
                        title="## Settings",
                        children=[
                            Actions(
                                [
                                    Action("Send", on_click=noop),
                                    Action("Docs", url="https://x.test"),
                                ]
                            )
                        ],
                    )
                ]
            )
        )
        rows = [c for c in payload[0]["components"] if c["type"] == _ACTION_ROW]
        assert len(rows) == 1
        assert [b["label"] for b in rows[0]["components"]] == ["Send", "Docs"]

    def test_more_than_five_actions_wrap_instead_of_breaking(self):
        payload = build(
            Page(
                body=[Card(children=[Actions([Action(f"b{i}", on_click=noop) for i in range(7)])])]
            )
        )
        rows = [c for c in payload[0]["components"] if c["type"] == _ACTION_ROW]
        assert [len(r["components"]) for r in rows] == [5, 2]

    def test_action_without_handler_or_url_is_disabled(self):
        payload = build(Page(body=[Card(children=[Actions([Action("Inert")])])]))
        row = next(c for c in payload[0]["components"] if c["type"] == _ACTION_ROW)
        assert row["components"][0]["disabled"] is True

    def test_link_action_stays_enabled(self):
        payload = build(
            Page(body=[Card(children=[Actions([Action("Docs", url="https://x.test")])])])
        )
        row = next(c for c in payload[0]["components"] if c["type"] == _ACTION_ROW)
        assert row["components"][0]["disabled"] is False


class TestCardSelect:
    def test_select_takes_its_own_row(self):
        """A select owns its row and must not join the buttons before it."""
        payload = build(
            Page(
                body=[
                    Card(
                        children=[
                            Actions([Action("Back", on_click=noop)]),
                            Select(
                                kind="string",
                                options=[discord.SelectOption(label="A", value="a")],
                                on_change=noop,
                            ),
                        ]
                    )
                ]
            )
        )
        rows = [c for c in payload[0]["components"] if c["type"] == _ACTION_ROW]
        assert [c["type"] for c in rows[0]["components"]] == [_BUTTON]
        assert [c["type"] for c in rows[1]["components"]] == [_STRING_SELECT]

    @pytest.mark.parametrize(
        "kind,expected", [("role", 6), ("channel", 8), ("user", 5), ("mentionable", 7)]
    )
    def test_entity_selects_map_to_their_component_type(self, kind, expected):
        payload = build(Page(body=[Card(children=[Select(kind=kind, on_change=noop)])]))
        row = next(c for c in payload[0]["components"] if c["type"] == _ACTION_ROW)
        assert row["components"][0]["type"] == expected

    def test_select_without_handler_is_disabled(self):
        payload = build(Page(body=[Card(children=[Select(kind="role")])]))
        row = next(c for c in payload[0]["components"] if c["type"] == _ACTION_ROW)
        assert row["components"][0]["disabled"] is True

    def test_unknown_kind_is_rejected(self):
        with pytest.raises(ValueError, match="unknown select kind"):
            build(Page(body=[Card(children=[Select(kind="colour", on_change=noop)])]))


class TestTabBar:
    def test_active_tab_is_primary_and_unclickable(self):
        payload = build(
            Page(
                tabs=TabBar(
                    tabs=[Tab("Pending", "pending"), Tab("Done", "done")],
                    active="pending",
                    on_change=noop,
                ),
                body=[Card(title="## A")],
            )
        )
        buttons = payload[0]["components"]
        assert buttons[0]["style"] == discord.ButtonStyle.primary.value
        assert buttons[0]["disabled"] is True
        assert buttons[1]["style"] == discord.ButtonStyle.secondary.value
        assert buttons[1]["disabled"] is False

    def test_six_tabs_fall_back_to_a_select(self):
        tabs = [Tab(f"t{i}", str(i)) for i in range(6)]
        payload = build(Page(tabs=TabBar(tabs=tabs, active="3", on_change=noop), body=[Card()]))
        row = payload[0]["components"]
        assert [c["type"] for c in row] == [_STRING_SELECT]
        options = row[0]["options"]
        assert len(options) == 6
        assert [o["value"] for o in options if o.get("default")] == ["3"]

    def test_five_tabs_stay_buttons(self):
        tabs = [Tab(f"t{i}", str(i)) for i in range(5)]
        payload = build(Page(tabs=TabBar(tabs=tabs, on_change=noop), body=[Card()]))
        assert all(c["type"] == _BUTTON for c in payload[0]["components"])


class TestPager:
    def _row(self, **kwargs):
        payload = build(Page(body=[Card(title="## A")], pager=Pager(**kwargs)))
        return payload[1]["components"]

    def test_five_buttons_fill_the_row(self):
        row = self._row(current=3, total=12, on_change=noop)
        assert len(row) == 5

    def test_center_shows_current_over_total(self):
        row = self._row(current=3, total=12, on_change=noop)
        assert row[2]["label"] == "3 / 12"

    def test_first_page_disables_backwards_buttons(self):
        row = self._row(current=1, total=12, on_change=noop)
        assert [b["disabled"] for b in row] == [True, True, False, False, False]

    def test_last_page_disables_forwards_buttons(self):
        row = self._row(current=12, total=12, on_change=noop)
        assert [b["disabled"] for b in row] == [False, False, False, True, True]

    def test_single_page_disables_the_jump(self):
        row = self._row(current=1, total=1, on_change=noop)
        assert row[2]["disabled"] is True

    def test_out_of_range_current_is_clamped(self):
        row = self._row(current=99, total=12, on_change=noop)
        assert row[2]["label"] == "12 / 12"


class TestActionBar:
    def test_only_handled_buttons_appear(self):
        payload = build(
            Page(body=[Card(title="## A")], actions=ActionBar(on_reload=noop, on_back=noop))
        )
        labels = [b["label"] for b in payload[1]["components"]]
        assert labels == ["Reload", "Back"]

    def test_order_is_reload_back_close(self):
        payload = build(
            Page(
                body=[Card(title="## A")],
                actions=ActionBar(on_reload=noop, on_back=noop, on_close=noop),
            )
        )
        labels = [b["label"] for b in payload[1]["components"]]
        assert labels == ["Reload", "Back", "Close"]


class TestBudget:
    def test_too_many_top_level_slots_is_caught_before_sending(self):
        page = Page(
            tabs=TabBar(tabs=[Tab("a", "a")], on_change=noop),
            body=[Card(title=f"## {i}") for i in range(9)],
            pager=Pager(current=1, total=2, on_change=noop),
        )
        with pytest.raises(LimitError, match="top-level components"):
            page.build()

    def test_too_many_components_is_caught_before_sending(self):
        page = Page(
            body=[
                Card(
                    title="## Settings",
                    children=[
                        SettingRow(f"k{i}", "v", action="Change", on_click=noop) for i in range(15)
                    ],
                )
            ]
        )
        with pytest.raises(LimitError, match="components"):
            page.build()


class TestJumpModal:
    @pytest.mark.parametrize("raw", ["0", "13", "abc", ""])
    async def test_invalid_input_is_rejected(self, raw, monkeypatch):
        sent = {}

        class _Response:
            async def send_message(self, content, ephemeral=False):
                sent["content"] = content
                sent["ephemeral"] = ephemeral

        class _Interaction:
            response = _Response()

        called = []

        async def on_change(interaction, page):
            called.append(page)

        from kagekit.theme import DEFAULT_THEME

        modal = JumpModal(theme=DEFAULT_THEME, total=12, on_change=on_change)
        monkeypatch.setattr(type(modal.page_input), "value", raw, raising=False)
        await modal.on_submit(_Interaction())

        assert called == []
        assert "12" in sent["content"]
        assert sent["ephemeral"] is True

    async def test_valid_input_calls_the_handler(self, monkeypatch):
        called = []

        async def on_change(interaction, page):
            called.append(page)

        from kagekit.theme import DEFAULT_THEME

        modal = JumpModal(theme=DEFAULT_THEME, total=12, on_change=on_change)
        monkeypatch.setattr(type(modal.page_input), "value", "7", raising=False)
        await modal.on_submit(object())

        assert called == [7]
