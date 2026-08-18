"""The low layer — a builder for the Components V2 primitives.

``ComponentBuilder`` assembles containers, sections, action rows and selects by method
chaining. The declarative layer (Page / Card / TabBar / Pager / ActionBar) sits on top
of it. Reach for the builder directly when you need something the declarative layer
does not model.

.. note::
   This module imports nothing but discord.py and the standard library. Branding and
   wording arrive as :class:`kagekit.theme.Theme`.
"""

from __future__ import annotations

from typing import Optional, Union

import discord
from discord import ui

from .theme import DEFAULT_THEME, Theme

#: Emoji accepted by a button or a section accessory. discord.py takes either a
#: unicode string or a custom emoji object.
EmojiInput = Optional[Union[str, discord.Emoji, discord.PartialEmoji]]

#: Views the send helpers accept. ``LayoutView`` is not a subclass of the classic
#: ``View`` (their common base is private), so both are named explicitly.
ViewLike = Union[ui.View, ui.LayoutView]


class ComponentBuilder:
    """Builds a Components V2 view by method chaining.

    .. warning::
        A message using Components V2 cannot carry ``content``, ``embed`` or
        ``embeds``. Discord rejects it with
        ``In content: The 'content' field cannot be used when using
        MessageFlags.IS_COMPONENTS_V2`` (and the equivalent for embeds), so every piece
        of information has to be built here as ``text`` or ``section``. If you need a
        plain body or an embed alongside buttons, use a classic ``discord.ui.View``
        instead of this builder.
    """

    class _ContainerBackedSection:
        """
        A stand-in that satisfies the minimal ``ui.Section`` interface.

        It simply appends items straight to the container.
        """

        def __init__(self, container: ui.Container):
            self._container = container

        def add_item(self, item):
            if isinstance(item, ui.TextDisplay) and self._container.children:
                previous = self._container.children[-1]
                if isinstance(previous, ui.TextDisplay):
                    merged = f"{previous.content}\n{item.content}"
                    if len(merged) <= 4000:
                        previous.content = merged
                        return
            self._container.add_item(item)

        def remove_item(self, item):
            raise NotImplementedError

    def __init__(
        self,
        is_premium: bool = False,
        *,
        theme: Theme = DEFAULT_THEME,
    ):
        #: A compatibility flag hosts may read. KageKit has no billing concept.
        self.is_premium: bool = is_premium
        #: Where palette, wording and branding are injected.
        self.theme: Theme = theme
        self._top_level: list[ui.Item] = []
        self._current_container = ui.Container()
        self._current_section: Optional[ui.Section] = None
        self._current_actionrow: Optional[ui.ActionRow] = None

    @staticmethod
    def is_components_v2_view(view: Optional[ViewLike]) -> bool:
        """Whether the view carries Components V2."""
        return bool(view and getattr(view, "has_components_v2", lambda: False)())

    @staticmethod
    async def send_interaction_response(
        interaction: discord.Interaction,
        view: ViewLike,
        *,
        ephemeral: bool = True,
    ):
        """
        Send a view to an interaction safely.

        discord.py 2.7.x puts ``content=None`` in the payload even when no content was
        given, which Discord rejects for a Components V2 message. A V2 view is therefore
        deferred first and sent as a follow-up, so the content field is never present.
        """
        if ComponentBuilder.is_components_v2_view(view):
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=ephemeral)
            return await interaction.followup.send(view=view, ephemeral=ephemeral)

        if interaction.response.is_done():
            return await interaction.followup.send(view=view, ephemeral=ephemeral)
        return await interaction.response.send_message(view=view, ephemeral=ephemeral)

    @staticmethod
    async def edit_interaction_response(
        interaction: discord.Interaction,
        view: Optional[ViewLike],
    ):
        """
        Replace the interaction's message with a view, safely.

        Switching a plain message to a ``LayoutView`` hits the Components V2 restriction
        unless the existing content, embed and attachments are cleared explicitly; that
        is handled here.
        """
        kwargs = {"view": view}
        if ComponentBuilder.is_components_v2_view(view):
            kwargs.update({"content": None, "embed": None, "attachments": []})
        return await interaction.response.edit_message(**kwargs)

    def _flush_container(self) -> None:
        """Close the container being assembled and push it onto the top level."""
        if self._current_container.children:
            self._top_level.append(self._current_container)
            self._current_container = ui.Container()

    def container(self, accent_color: Optional[int] = None) -> ComponentBuilder:
        """Start a new container — a card.

        The layout contract says content that is genuinely different gets its own card.
        Pass ``accent_color`` from ``theme.palette``; never a hex literal.
        """
        self._flush_container()
        if accent_color is None:
            self._current_container = ui.Container()
        else:
            self._current_container = ui.Container(accent_color=accent_color)
        self._current_section = None
        self._current_actionrow = None
        return self

    def section(
        self,
        title: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        *,
        raw: bool = False,
        button_label: Optional[str] = None,
        button_callback: Optional[callable] = None,
        button_style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        button_emoji: EmojiInput = None,
        button_url: Optional[str] = None,
        button_disabled: bool = False,
        button_custom_id: Optional[str] = None,
    ) -> ComponentBuilder:
        """Start a new section.

        Passing ``button_label`` produces a real ``ui.Section`` with a button as its
        accessory — the "description text plus one action" shape. A section takes exactly one
        accessory, so ``thumbnail_url`` is mutually exclusive with it; if both are given
        the button wins. With neither, you get the container-backed pseudo-section.

        While a section has an accessory, ``_current_section`` keeps pointing at it, so a
        following ``text()`` is added as another description line of that same section
        (three at most).

        ``title`` is formatted as a ``## `` heading by default, and left alone when it
        already starts with ``#``. Pass ``raw=True`` to use pre-formatted text — bold,
        say — as the heading without the ``## `` prefix.
        """
        if title:
            if raw or title.startswith("#"):
                display_text = title
            else:
                display_text = f"## {title}"
            display = ui.TextDisplay(display_text)
        else:
            display = None

        if button_label is not None:
            accessory = self._build_button(
                label=button_label,
                style=button_style,
                url=button_url,
                disabled=button_disabled,
                custom_id=button_custom_id,
                emoji=button_emoji,
                callback=button_callback,
            )
        elif thumbnail_url:
            accessory = ui.Thumbnail(thumbnail_url)
        else:
            accessory = None

        if accessory is not None:
            if display is None:
                display = ui.TextDisplay("")
            sec = ui.Section(display, accessory=accessory)
            self._current_section = sec
            self._current_container.add_item(sec)
        else:
            if display is not None:
                self._current_container.add_item(display)
            self._current_section = ComponentBuilder._ContainerBackedSection(
                self._current_container
            )

        return self

    def setting_section(
        self,
        label: str,
        value: str,
        *,
        emoji: str = "",
        extra: Optional[str] = None,
        button_label: Optional[str] = None,
        button_callback: Optional[callable] = None,
        button_style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        button_emoji: EmojiInput = None,
        button_disabled: bool = False,
        separator: bool = True,
    ) -> ComponentBuilder:
        """Render one setting in the shared shape.

        The layout every panel uses: ``**{emoji} {label}**: {value}`` as the text, with
        the edit or toggle button as the section's accessory. ``extra`` adds further
        lines below. Omit ``button_label`` for a read-only row.

        A separator precedes each row by default (``separator=False`` suppresses it).
        Emit headings through ``section()`` as well — a bare ``text()`` right after a
        real section leaks into it.
        """
        if separator:
            self.separator()
        head = f"**{(emoji + ' ') if emoji else ''}{label}**：{value}"
        if extra:
            head += f"\n{extra}"
        self.section(
            head,
            raw=True,
            button_label=button_label,
            button_callback=button_callback,
            button_style=button_style,
            button_emoji=button_emoji,
            button_disabled=button_disabled,
        )
        return self

    def text(self, content: str, code_block: bool = False) -> ComponentBuilder:
        """Add text, falling back to the container once a section holds three children."""
        if code_block:
            content = f"```{content}```"

        if not self._current_section:
            self._current_section = ComponentBuilder._ContainerBackedSection(
                self._current_container
            )

        is_section = isinstance(self._current_section, ui.Section)

        if is_section:
            children = getattr(self._current_section, "children", None)
            if children is None:
                self._current_section = ComponentBuilder._ContainerBackedSection(
                    self._current_container
                )
                self._current_section.add_item(ui.TextDisplay(content))
                return self

            if len(children) >= 3:
                self._current_section = ComponentBuilder._ContainerBackedSection(
                    self._current_container
                )
                self._current_section.add_item(ui.TextDisplay(content))
                return self

            self._current_section.add_item(ui.TextDisplay(content))
            return self

        self._current_section.add_item(ui.TextDisplay(content))
        return self

    def separator(
        self,
        visible: bool = True,
        spacing: discord.SeparatorSpacing = discord.SeparatorSpacing.small,
    ) -> ComponentBuilder:
        """Add a separator."""
        self._current_container.add_item(ui.Separator(visible=visible, spacing=spacing))
        return self

    def end_section(self) -> ComponentBuilder:
        """Close the section being assembled so later items land in the container.

        Calling ``text()`` straight after a real section (one with an accessory) is
        swallowed by that section while it holds fewer than three children. Call this
        first when a heading or a note must not leak into the row above it.
        """
        self._current_section = None
        return self

    def action_row(self) -> ComponentBuilder:
        """Start an action row **inside** the current container."""
        self._current_actionrow = ui.ActionRow()
        self._current_container.add_item(self._current_actionrow)
        return self

    def outer_action_row(self) -> ComponentBuilder:
        """Put an action row **outside** every container, at the top level.

        The layout contract places section switches at the very top and reload / back /
        close at the very bottom. Both are top-level action rows rather than rows inside
        a container, which is why this exists separately from ``action_row()``.

        Subsequent ``button()`` / ``add_item()`` calls land in this row; calling
        ``container()`` returns to building inside a card. Five buttons per row.
        """
        self._flush_container()
        row = ui.ActionRow()
        self._top_level.append(row)
        self._current_actionrow = row
        self._current_section = None
        return self

    @staticmethod
    def _build_button(
        label: str,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        url: Optional[str] = None,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        emoji: EmojiInput = None,
        row: Optional[int] = None,
        callback: Optional[callable] = None,
    ) -> ui.Button:
        """Build a ``ui.Button``, shared by action rows and section accessories."""
        if url:
            return ui.Button(
                style=discord.ButtonStyle.url,
                label=label,
                url=url,
                disabled=disabled,
                emoji=emoji,
                row=row,
            )

        kwargs = {
            "style": style,
            "label": label,
            "disabled": disabled,
            "emoji": emoji,
            "row": row,
        }
        if custom_id is not None:
            kwargs["custom_id"] = custom_id
        button = ui.Button(**kwargs)
        if callback:
            button.callback = callback
        return button

    def button(
        self,
        label: str,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        url: Optional[str] = None,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        emoji: EmojiInput = None,
        row: Optional[int] = None,
        callback: Optional[callable] = None,
    ) -> ComponentBuilder:
        """Add a button."""
        if not self._current_actionrow:
            self.action_row()

        button = self._build_button(
            label=label,
            style=style,
            url=url,
            disabled=disabled,
            custom_id=custom_id,
            emoji=emoji,
            row=row,
            callback=callback,
        )
        self._current_actionrow.add_item(button)
        return self

    def add_item(self, item) -> ComponentBuilder:
        """Add an already-built ``ui.Item`` to the current action row.

        For custom ``Select`` / ``Button`` subclasses carrying their own callback — the
        components the ``*_select`` helpers cannot express.
        """
        if not self._current_actionrow:
            self.action_row()
        self._current_actionrow.add_item(item)
        return self

    # --- Select Methods ---
    def string_select(
        self,
        options: list[discord.SelectOption],
        placeholder: Optional[str] = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        row: Optional[int] = None,
        callback: Optional[callable] = None,
    ) -> ComponentBuilder:
        """Add a string select."""
        kwargs = {
            "options": options,
            "placeholder": placeholder,
            "min_values": min_values,
            "max_values": max_values,
            "disabled": disabled,
            "row": row,
        }
        if custom_id is not None:
            kwargs["custom_id"] = custom_id
        select = ui.Select(**kwargs)
        if callback:
            select.callback = callback
        if not self._current_actionrow:
            self.action_row()
        self._current_actionrow.add_item(select)
        return self

    def channel_select(
        self,
        channel_types: Optional[list[discord.ChannelType]] = None,
        placeholder: Optional[str] = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        row: Optional[int] = None,
        callback: Optional[callable] = None,
        default_values: Optional[list] = None,
    ) -> ComponentBuilder:
        """Add a channel select."""
        kwargs = {
            "channel_types": channel_types,
            "placeholder": placeholder,
            "min_values": min_values,
            "max_values": max_values,
            "disabled": disabled,
            "row": row,
        }
        if custom_id is not None:
            kwargs["custom_id"] = custom_id
        if default_values:
            # accepts a discord.abc.GuildChannel or a discord.SelectDefaultValue
            kwargs["default_values"] = default_values
        select = ui.ChannelSelect(**kwargs)
        if callback:
            select.callback = callback
        if not self._current_actionrow:
            self.action_row()
        self._current_actionrow.add_item(select)
        return self

    def role_select(
        self,
        placeholder: Optional[str] = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        row: Optional[int] = None,
        callback: Optional[callable] = None,
        default_values: Optional[list] = None,
    ) -> ComponentBuilder:
        """Add a role select."""
        kwargs = {
            "placeholder": placeholder,
            "min_values": min_values,
            "max_values": max_values,
            "disabled": disabled,
            "row": row,
        }
        if custom_id is not None:
            kwargs["custom_id"] = custom_id
        if default_values:
            # accepts a discord.Role or a discord.Object(type=discord.Role)
            kwargs["default_values"] = default_values
        select = ui.RoleSelect(**kwargs)
        if callback:
            select.callback = callback
        if not self._current_actionrow:
            self.action_row()
        self._current_actionrow.add_item(select)
        return self

    def user_select(
        self,
        placeholder: Optional[str] = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        row: Optional[int] = None,
        callback: Optional[callable] = None,
        default_values: Optional[list] = None,
    ) -> ComponentBuilder:
        """Add a user select."""
        kwargs = {
            "placeholder": placeholder,
            "min_values": min_values,
            "max_values": max_values,
            "disabled": disabled,
            "row": row,
        }
        if custom_id is not None:
            kwargs["custom_id"] = custom_id
        if default_values:
            # accepts a discord.Member/User or a discord.SelectDefaultValue
            kwargs["default_values"] = default_values
        select = ui.UserSelect(**kwargs)
        if callback:
            select.callback = callback
        if not self._current_actionrow:
            self.action_row()
        self._current_actionrow.add_item(select)
        return self

    def mentionable_select(
        self,
        placeholder: Optional[str] = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        row: Optional[int] = None,
        callback: Optional[callable] = None,
    ) -> ComponentBuilder:
        """Add a mentionable select."""
        kwargs = {
            "placeholder": placeholder,
            "min_values": min_values,
            "max_values": max_values,
            "disabled": disabled,
            "row": row,
        }
        if custom_id is not None:
            kwargs["custom_id"] = custom_id
        select = ui.MentionableSelect(**kwargs)
        if callback:
            select.callback = callback
        if not self._current_actionrow:
            self.action_row()
        self._current_actionrow.add_item(select)
        return self

    def _append_footer(self) -> None:
        """Append ``theme.footer`` to the last card as subtext, when set.

        A separator plus a ``-#`` line is added to the end of the last container, or a
        new container if there is none. A theme with no footer changes nothing.
        """
        if not self.theme.footer:
            return
        branding = f"-# {self.theme.footer}"
        target = None
        for item in reversed(self._top_level):
            if isinstance(item, ui.Container):
                target = item
                break
        if target is None:
            target = ui.Container()
            self._top_level.append(target)
        if target.children:
            target.add_item(ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
        target.add_item(ui.TextDisplay(branding))

    def build(self) -> ui.LayoutView:
        """Build the view.

        The top level holds outer action rows and containers in the order they were
        added. Discord allows 10 top-level components and 40 in total.
        """
        self._flush_container()

        # Append the theme's footer, when it has one, to every V2 message.
        self._append_footer()

        view = ui.LayoutView(timeout=None)
        for item in self._top_level:
            view.add_item(item)

        # reset the builder
        self._top_level = []
        self._current_container = ui.Container()
        self._current_section = None
        self._current_actionrow = None

        return view
