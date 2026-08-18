"""The declarative layer — describe a panel, and the layout is decided for you.

``ComponentBuilder`` can assemble anything, which leaves the layout contract — what
goes where — to the author's self-discipline. This module turns that contract into
types and structure, so the violations cannot be written.

.. code-block:: python

    Page(
        tabs=TabBar(tabs=[Tab("Pending", "pending"), Tab("Done", "done")],
                    active="pending", on_change=self.switch),
        body=[
            Card(title="🎫 Ticket settings", intent="brand", children=[
                SettingRow("Category", "Support", emoji="📂",
                           action="Change", on_click=self.edit_category),
            ]),
            Card(title="Delete every ticket", intent="danger", children=[
                Text("This cannot be undone."),
            ]),
        ],
        pager=Pager(current=3, total=12, on_change=self.goto),
        actions=ActionBar(on_reload=self.reload, on_back=self.back),
    )

The placements are fixed:

* ``tabs``    — outside the container, at the top; switches what the page is showing
* ``body``    — the cards; a different subject gets a different card
* ``pager``   — its own row; moves through the contents inside a card
* ``actions`` — outside the container, at the bottom; acts on the whole message

.. note::
   This module imports nothing but discord.py and the standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping, Optional, Sequence, Union

import discord
from discord import ui

from .builder import ComponentBuilder
from .errors import LimitError
from .theme import DEFAULT_THEME, Theme

#: A handler taking nothing but the interaction — the press is the whole signal.
Handler = Callable[[discord.Interaction], Awaitable[None]]
#: A handler receiving the chosen value (TabBar).
ValueHandler = Callable[[discord.Interaction, str], Awaitable[None]]
#: A handler receiving the target page, 1-based (Pager).
PageHandler = Callable[[discord.Interaction, int], Awaitable[None]]
#: A handler receiving the list of selected values (Select).
ValuesHandler = Callable[[discord.Interaction, list], Awaitable[None]]

#: Discord's own limits (as of 2026-08).
MAX_TOP_LEVEL = 10
MAX_COMPONENTS = 40
MAX_BUTTONS_PER_ROW = 5

#: intent name -> attribute on Palette
_INTENTS = ("brand", "success", "warning", "danger", "info", "neutral")


def state_intent(enabled: bool) -> str:
    """The accent for a feature card: ``success`` when on, ``neutral`` when off.

    State then reads from the colour as well as the text.
    """
    return "success" if enabled else "neutral"


# ------------------------------------------------------------- card children
@dataclass
class Text:
    """Plain text inside a card. Write ``## `` yourself for a heading."""

    content: str
    code_block: bool = False


@dataclass
class Divider:
    """A separator line inside a card."""

    visible: bool = True


@dataclass
class Heading:
    """A sub-heading inside a card.

    ``thumbnail`` hangs an image off the right of it (the section's accessory).
    ``raw=True`` skips the ``## `` prefix and prints pre-formatted text as given.
    """

    text: Optional[str] = None
    thumbnail: Optional[str] = None
    raw: bool = False


@dataclass
class SettingRow:
    """One setting: its value and the control that changes it, on the same row.

    Renders ``**{emoji} {label}**: {value}`` with the button as the section's accessory.
    Omit ``action`` for a read-only row.
    """

    label: str
    value: str
    emoji: str = ""
    extra: Optional[str] = None
    action: Optional[str] = None
    action_emoji: Optional[str] = None
    on_click: Optional[Handler] = None
    style: discord.ButtonStyle = discord.ButtonStyle.secondary
    disabled: bool = False
    separator: bool = True


@dataclass
class Action:
    """A single button inside a card. Put it in ``Actions``."""

    label: str
    on_click: Optional[Handler] = None
    style: discord.ButtonStyle = discord.ButtonStyle.secondary
    emoji: Optional[str] = None
    url: Optional[str] = None
    disabled: bool = False
    #: A stable id for persistent views. Omitted, discord.py generates one.
    custom_id: Optional[str] = None


@dataclass
class Actions:
    """A row of buttons inside a card.

    For operations on *that card's* subject — "send the panel", "docs". Message-wide
    controls belong in ``ActionBar``. Past five, the row wraps automatically.
    """

    items: Sequence[Action]


@dataclass
class Select:
    """A select inside a card.

    ``kind`` is ``string`` / ``role`` / ``channel`` / ``user`` / ``mentionable``.
    ``on_change`` receives the list of selected values as strings.
    """

    kind: str = "string"
    options: Sequence[discord.SelectOption] = field(default_factory=tuple)
    placeholder: Optional[str] = None
    min_values: int = 1
    max_values: int = 1
    default_values: Optional[Sequence[object]] = None
    channel_types: Optional[Sequence[discord.ChannelType]] = None
    on_change: Optional[ValuesHandler] = None
    disabled: bool = False
    #: A stable id for persistent views. Omitted, discord.py generates one.
    custom_id: Optional[str] = None


@dataclass
class Control:
    """Drop a raw ``discord.ui.Item`` into a card.

    The escape hatch for persistent-view subclasses that ``Select`` and ``Actions``
    cannot express.
    """

    item: ui.Item


CardChild = Union[Text, Heading, Divider, SettingRow, Actions, Select, Control]


@dataclass
class Card:
    """One card, i.e. one Container. **Content that differs gets its own card.**

    Colour comes from ``intent`` (brand/success/warning/danger/info/neutral). Wanting a
    hex literal means the palette is missing a token — add one in ``kagekit/tokens.py``.
    ``accent`` is the escape hatch for migrations and genuine brand colours.
    """

    title: Optional[str] = None
    intent: Optional[str] = None
    accent: Optional[int] = None
    children: Sequence[CardChild] = field(default_factory=tuple)

    def resolve_accent(self, theme: Theme) -> Optional[int]:
        if self.accent is not None:
            return self.accent
        if self.intent is None:
            return None
        if self.intent not in _INTENTS:
            raise ValueError(f"unknown intent {self.intent!r} (expected one of {_INTENTS})")
        return int(getattr(theme.palette, self.intent))


# ----------------------------------------------------------- the outer rows
@dataclass
class Tab:
    """One section switch — pending / running / done, and so on."""

    label: str
    value: str
    emoji: Optional[str] = None


@dataclass
class TabBar:
    """The section switches, placed **outside the container, at the top**.

    Up to five render as a row of buttons; six or more become a string select, because
    a row holds five buttons and overflowing it breaks the build.
    """

    tabs: Sequence[Tab]
    active: Optional[str] = None
    on_change: Optional[ValueHandler] = None
    placeholder: Optional[str] = None


@dataclass
class Pager:
    """Paging. ``current`` is 1-based.

    The middle button shows ``current / total`` and opens a modal to jump. The outer
    buttons step one page and jump to either end. Five buttons — exactly one row.
    """

    current: int
    total: int
    on_change: Optional[PageHandler] = None
    jump: bool = True


@dataclass
class ActionBar:
    """Message-wide controls, placed **outside the container, at the bottom**.

    Only the buttons you passed a handler for are rendered.
    """

    on_reload: Optional[Handler] = None
    on_back: Optional[Handler] = None
    on_close: Optional[Handler] = None
    #: Extra buttons after the standard ones — a documentation link, typically.
    extra: Sequence[Action] = field(default_factory=tuple)


# ---------------------------------------------------------------------- Modal
class JumpModal(ui.Modal):
    """The jump-to-page modal opened by the Pager's middle button."""

    def __init__(self, *, theme: Theme, total: int, on_change: PageHandler) -> None:
        super().__init__(title=theme.labels.jump_title, timeout=None)
        self._theme = theme
        self._total = total
        self._on_change = on_change
        self.page_input: ui.TextInput = ui.TextInput(
            label=theme.labels.jump_field,
            placeholder=f"1-{total}",
            max_length=len(str(total)),
            required=True,
        )
        self.add_item(self.page_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = (self.page_input.value or "").strip()
        if not raw.isdigit() or not 1 <= int(raw) <= self._total:
            await interaction.response.send_message(
                self._theme.labels.jump_invalid.format(total=self._total),
                ephemeral=True,
            )
            return
        await self._on_change(interaction, int(raw))


# ----------------------------------------------------------------------- Page
@dataclass
class Page:
    """One message worth of panel.

    ``build()`` returns the ``LayoutView``; ``send()`` and ``edit()`` deliver it. Editing
    the same message in place is the canonical pattern — coming back from a sub-panel
    uses ``edit()`` rather than stacking another ephemeral.
    """

    body: Sequence[Card] = field(default_factory=tuple)
    tabs: Optional[TabBar] = None
    pager: Optional[Pager] = None
    actions: Optional[ActionBar] = None
    theme: Theme = DEFAULT_THEME

    # -- assembly ---------------------------------------------------------
    def build(self) -> ui.LayoutView:
        cb = ComponentBuilder(theme=self.theme)

        if self.tabs is not None:
            self._render_tabs(cb, self.tabs)
        for card in self.body:
            self._render_card(cb, card)
        if self.pager is not None:
            self._render_pager(cb, self.pager)
        if self.actions is not None:
            self._render_actions(cb, self.actions)

        try:
            view = cb.build()
        except ValueError as exc:
            # discord.py rejected it at the 40-component cap. Translate that into a
            # LimitError that says what to cut.
            raise LimitError(
                f"components exceed Discord's cap of {MAX_COMPONENTS} "
                "(split settings into another card or sub-panel, or drop separators): "
                f"{exc}"
            ) from exc
        self._check_budget(view)
        return view

    async def send(self, interaction: discord.Interaction, *, ephemeral: bool = True) -> None:
        """Send the first message; the builder absorbs the V2 content restriction."""
        await ComponentBuilder.send_interaction_response(
            interaction, self.build(), ephemeral=ephemeral
        )

    async def edit(self, interaction: discord.Interaction) -> None:
        """Replace the same message in place — the canonical pattern."""
        await ComponentBuilder.edit_interaction_response(interaction, self.build())

    # -- the pieces -------------------------------------------------------
    def _render_tabs(self, cb: ComponentBuilder, tabs: TabBar) -> None:
        if not tabs.tabs:
            return
        cb.outer_action_row()

        if len(tabs.tabs) > MAX_BUTTONS_PER_ROW:
            options = [
                discord.SelectOption(
                    label=tab.label,
                    value=tab.value,
                    emoji=tab.emoji,
                    default=tab.value == tabs.active,
                )
                for tab in tabs.tabs
            ]
            cb.string_select(
                options=options,
                placeholder=tabs.placeholder,
                callback=self._value_callback(tabs.on_change),
            )
            return

        for tab in tabs.tabs:
            is_active = tab.value == tabs.active
            cb.button(
                label=tab.label,
                emoji=tab.emoji,
                style=(discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary),
                # the current tab is not clickable — no button that does nothing
                disabled=is_active or tabs.on_change is None,
                callback=self._tab_callback(tabs.on_change, tab.value),
            )

    def _render_card(self, cb: ComponentBuilder, card: Card) -> None:
        cb.container(card.resolve_accent(self.theme))
        if card.title:
            cb.section(card.title)

        for child in card.children:
            if isinstance(child, Text):
                # close the section first: text() after a real one leaks into it
                cb.end_section().text(child.content, code_block=child.code_block)
            elif isinstance(child, Heading):
                cb.section(child.text, thumbnail_url=child.thumbnail, raw=child.raw)
            elif isinstance(child, Divider):
                cb.separator(visible=child.visible)
            elif isinstance(child, Actions):
                self._render_card_actions(cb, child)
            elif isinstance(child, Select):
                self._render_select(cb, child)
            elif isinstance(child, Control):
                cb.action_row()
                cb.add_item(child.item)
            elif isinstance(child, SettingRow):
                cb.setting_section(
                    child.label,
                    child.value,
                    emoji=child.emoji,
                    extra=child.extra,
                    button_label=child.action,
                    button_emoji=child.action_emoji,
                    button_callback=child.on_click,
                    button_style=child.style,
                    button_disabled=child.disabled or child.on_click is None,
                    separator=child.separator,
                )
            else:  # pragma: no cover - the type union rules this out
                raise TypeError(f"unsupported card child: {child!r}")

    @staticmethod
    def _render_card_actions(
        cb: ComponentBuilder, actions: Actions, *, outer: bool = False
    ) -> None:
        items = list(actions.items)
        # Five buttons per row. Wrap rather than break silently.
        for start in range(0, len(items), MAX_BUTTONS_PER_ROW):
            cb.outer_action_row() if outer else cb.action_row()
            for action in items[start : start + MAX_BUTTONS_PER_ROW]:
                cb.button(
                    label=action.label,
                    style=action.style,
                    url=action.url,
                    emoji=action.emoji,
                    custom_id=action.custom_id,
                    disabled=action.disabled or (action.on_click is None and action.url is None),
                    callback=action.on_click,
                )

    @staticmethod
    def _render_select(cb: ComponentBuilder, select: Select) -> None:
        # A select owns its row, so open a new one instead of joining the buttons.
        cb.action_row()
        callback = Page._values_callback(select.on_change)
        common = {
            "placeholder": select.placeholder,
            "min_values": select.min_values,
            "max_values": select.max_values,
            "disabled": select.disabled or select.on_change is None,
            "callback": callback,
        }
        if select.custom_id is not None:
            common["custom_id"] = select.custom_id
        defaults = list(select.default_values) if select.default_values else None

        if select.kind == "string":
            cb.string_select(options=list(select.options), **common)
        elif select.kind == "role":
            cb.role_select(default_values=defaults, **common)
        elif select.kind == "channel":
            cb.channel_select(
                channel_types=list(select.channel_types) if select.channel_types else None,
                default_values=defaults,
                **common,
            )
        elif select.kind == "user":
            cb.user_select(default_values=defaults, **common)
        elif select.kind == "mentionable":
            cb.mentionable_select(**common)
        else:
            raise ValueError(f"unknown select kind {select.kind!r}")

    def _render_pager(self, cb: ComponentBuilder, pager: Pager) -> None:
        emojis = self.theme.emojis
        total = max(pager.total, 1)
        current = min(max(pager.current, 1), total)
        at_first = current <= 1
        at_last = current >= total

        cb.outer_action_row()
        cb.button(
            label="",
            emoji=emojis.first,
            disabled=at_first or pager.on_change is None,
            callback=self._page_callback(pager.on_change, 1),
        )
        cb.button(
            label="",
            emoji=emojis.prev,
            disabled=at_first or pager.on_change is None,
            callback=self._page_callback(pager.on_change, current - 1),
        )
        cb.button(
            label=self.theme.labels.page_format.format(current=current, total=total),
            style=discord.ButtonStyle.secondary,
            disabled=not pager.jump or pager.on_change is None or total <= 1,
            callback=self._jump_callback(pager.on_change, total),
        )
        cb.button(
            label="",
            emoji=emojis.next,
            disabled=at_last or pager.on_change is None,
            callback=self._page_callback(pager.on_change, current + 1),
        )
        cb.button(
            label="",
            emoji=emojis.last,
            disabled=at_last or pager.on_change is None,
            callback=self._page_callback(pager.on_change, total),
        )

    def _render_actions(self, cb: ComponentBuilder, actions: ActionBar) -> None:
        labels = self.theme.labels
        emojis = self.theme.emojis
        items = [
            Action(label, on_click=handler, emoji=emoji)
            for label, emoji, handler in (
                (labels.reload, emojis.reload, actions.on_reload),
                (labels.back, emojis.back, actions.on_back),
                (labels.close, emojis.close, actions.on_close),
            )
            if handler is not None
        ]
        items += list(actions.extra)
        if not items:
            return
        self._render_card_actions(cb, Actions(items), outer=True)

    # -- callback factories -----------------------------------------------
    @staticmethod
    def _value_callback(handler: Optional[ValueHandler]):
        async def callback(interaction: discord.Interaction) -> None:
            if handler is None:
                return
            data: Mapping[str, Any] = interaction.data or {}
            values = data.get("values") or []
            if values:
                await handler(interaction, str(values[0]))

        return callback

    @staticmethod
    def _values_callback(handler: Optional[ValuesHandler]):
        async def callback(interaction: discord.Interaction) -> None:
            if handler is None:
                return
            data: Mapping[str, Any] = interaction.data or {}
            await handler(interaction, list(data.get("values") or []))

        return callback

    @staticmethod
    def _tab_callback(handler: Optional[ValueHandler], value: str):
        async def callback(interaction: discord.Interaction) -> None:
            if handler is not None:
                await handler(interaction, value)

        return callback

    @staticmethod
    def _page_callback(handler: Optional[PageHandler], target: int):
        async def callback(interaction: discord.Interaction) -> None:
            if handler is not None:
                await handler(interaction, target)

        return callback

    def _jump_callback(self, handler: Optional[PageHandler], total: int):
        async def callback(interaction: discord.Interaction) -> None:
            if handler is None:
                return
            await interaction.response.send_modal(
                JumpModal(theme=self.theme, total=total, on_change=handler)
            )

        return callback

    # -- budget check -----------------------------------------------------
    @staticmethod
    def _check_budget(view: ui.LayoutView) -> None:
        """Fail on a limit before the message is sent.

        An API rejection after the fact is hard to read, so this raises at build time
        with the thing that is too many named in the message.
        """
        payload = view.to_components()
        if len(payload) > MAX_TOP_LEVEL:
            raise LimitError(
                f"top-level components: {len(payload)} > {MAX_TOP_LEVEL} "
                "(tabs, pager and action bar take 3 slots, leaving 7 for cards)"
            )
        total = _count_components(payload)
        if total > MAX_COMPONENTS:
            raise LimitError(
                f"components: {total} > {MAX_COMPONENTS} "
                "(split settings into another card or sub-panel, or drop separators)"
            )


def _count_components(node: object) -> int:
    """Count the components in a Components V2 payload."""
    if isinstance(node, list):
        return sum(_count_components(child) for child in node)
    if isinstance(node, dict):
        count = 1 if "type" in node else 0
        for key in ("components", "accessory", "component", "items"):
            if key in node:
                count += _count_components(node[key])
        return count
    return 0


def render_card(cb: ComponentBuilder, card: Card, *, theme: Theme = DEFAULT_THEME) -> None:
    """Render one card into an existing ``ComponentBuilder`` — a migration bridge.

    Lets code that has not moved to ``Page`` yet drop in a declaratively built card (an
    embed preview, say) while the card keeps a single definition. Delete it once nothing
    builds views by hand.
    """
    Page(theme=theme)._render_card(cb, card)
