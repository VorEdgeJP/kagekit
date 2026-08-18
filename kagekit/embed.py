"""An embed builder, for the contexts Components V2 cannot serve.

Plain messages, logs and outbound integrations still want an embed. Colours come from
:class:`kagekit.tokens.Palette` and caps arrive as :class:`kagekit.theme.Limits`.

.. note::
   This module imports nothing but discord.py and the standard library.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Union

from discord import Colour, Embed

from .errors import FeatureDisabledError, LimitError
from .theme import DEFAULT_THEME, UNLIMITED, Limits, Theme


class EmbedBuilder:
    """Builds an embed by method chaining, honouring the injected limits.

    ``to_dict`` / ``from_dict`` round-trip the state, so a host can persist a
    half-finished embed and restore it later.
    """

    def __init__(
        self,
        *,
        limits: Limits = UNLIMITED,
        ignore_limits: bool = False,
        theme: Theme = DEFAULT_THEME,
    ):
        self._limits: Limits = limits
        self._theme: Theme = theme
        self.ignore_limits: bool = ignore_limits
        self._title: Optional[str] = None
        self._description: Optional[str] = None
        self._color: Union[int, Colour] = Colour.default()
        self._url: Optional[str] = None
        self._timestamp: Optional[datetime] = None
        self._footer: Optional[dict] = None
        self._author: Optional[dict] = None
        self._thumbnail: Optional[str] = None
        self._image: Optional[str] = None
        self._fields: list[dict] = []

    # --- serialisation ---
    def to_dict(self) -> dict:
        """Export the current state as a JSON-serialisable dict."""
        timestamp_str = self._timestamp.isoformat() if self._timestamp else None
        return {
            "title": self._title,
            "description": self._description,
            "color": (self._color.value if isinstance(self._color, Colour) else self._color),
            "url": self._url,
            "timestamp": timestamp_str,
            "footer": self._footer,
            "author": self._author,
            "thumbnail": self._thumbnail,
            "image": self._image,
            "fields": self._fields,
        }

    @classmethod
    def from_dict(cls, data: dict, **kwargs) -> EmbedBuilder:
        """Restore a builder from a dict produced by :meth:`to_dict`.

        ``kwargs`` is forwarded to the constructor, so a subclass that takes its own
        arguments keeps working.
        """
        builder = cls(**kwargs)
        builder._title = data.get("title")
        builder._description = data.get("description")
        if color_val := data.get("color"):
            builder._color = Colour(color_val)
        builder._url = data.get("url")
        if ts_str := data.get("timestamp"):
            builder._timestamp = datetime.fromisoformat(ts_str)
        builder._footer = data.get("footer")
        builder._author = data.get("author")
        builder._thumbnail = data.get("thumbnail")
        builder._image = data.get("image")
        builder._fields = data.get("fields", [])
        return builder

    # --- templates ---
    def success(self, description: str, title: Optional[str] = None) -> EmbedBuilder:
        self._title = title if title is not None else self._theme.labels.success_title
        self._description = description
        self._color = Colour(self._theme.palette.success)
        self._timestamp = datetime.now()
        return self

    def error(self, description: str, title: Optional[str] = None) -> EmbedBuilder:
        self._title = title if title is not None else self._theme.labels.error_title
        self._description = description
        self._color = Colour(self._theme.palette.danger)
        self._timestamp = datetime.now()
        return self

    def warning(self, description: str, title: Optional[str] = None) -> EmbedBuilder:
        self._title = title if title is not None else self._theme.labels.warning_title
        self._description = description
        self._color = Colour(self._theme.palette.warning)
        self._timestamp = datetime.now()
        return self

    def info(self, description: str, title: Optional[str] = None) -> EmbedBuilder:
        self._title = title if title is not None else self._theme.labels.info_title
        self._description = description
        self._color = Colour(self._theme.palette.info)
        self._timestamp = datetime.now()
        return self

    # --- getters ---
    def get_title(self) -> Optional[str]:
        return self._title

    def get_description(self) -> Optional[str]:
        return self._description

    # --- setters ---
    def title(self, title: str) -> EmbedBuilder:
        self._title = title
        return self

    def description(self, description: str) -> EmbedBuilder:
        self._description = description
        return self

    def color(self, color: Union[int, Colour, str]) -> EmbedBuilder:
        if isinstance(color, str):
            try:
                self._color = Colour(int(color.replace("#", "0x"), 16))
            except (ValueError, TypeError):
                self._color = Colour.default()
        else:
            self._color = Colour(color) if isinstance(color, int) else color
        return self

    def footer(self, text: str, icon_url: Optional[str] = None) -> EmbedBuilder:
        self._footer = {"text": text, "icon_url": icon_url}
        return self

    def image(self, url: str) -> EmbedBuilder:
        self._image = url
        return self

    def thumbnail(self, url: str) -> EmbedBuilder:
        self._thumbnail = url
        return self

    def author(
        self, name: str, url: Optional[str] = None, icon_url: Optional[str] = None
    ) -> EmbedBuilder:
        self._author = {"name": name, "url": url, "icon_url": icon_url}
        return self

    def timestamp(self, time: Optional[datetime] = None) -> EmbedBuilder:
        self._timestamp = time or datetime.now()
        return self

    def url(self, url: str) -> EmbedBuilder:
        # Only the title link is gated. Image, thumbnail and author URLs are basic
        # features, so `embed_url_enabled` deliberately covers the title alone.
        if not self._limits.embed_url_enabled and not self.ignore_limits:
            raise FeatureDisabledError(self._theme.labels.feature_disabled)
        self._url = url
        return self

    def add_field(self, name: str, value: str, inline: bool = True) -> EmbedBuilder:
        max_fields = self._limits.max_embed_fields  # None = unlimited
        if not self.ignore_limits and max_fields is not None and len(self._fields) >= max_fields:
            raise LimitError(self._theme.labels.field_limit.format(max=max_fields))

        self._fields.append({"name": name, "value": str(value), "inline": inline})
        return self

    def edit_field(self, index: int, name: str, value: str, inline: bool = True) -> EmbedBuilder:
        """Replace the field at ``index``."""
        if 0 <= index < len(self._fields):
            self._fields[index] = {"name": name, "value": str(value), "inline": inline}
        else:
            raise IndexError("The specified index does not exist.")
        return self

    def remove_field(self, index: int) -> EmbedBuilder:
        """Remove the field at ``index``."""
        if 0 <= index < len(self._fields):
            self._fields.pop(index)
        else:
            raise IndexError("The specified index does not exist.")
        return self

    def clear_fields(self) -> EmbedBuilder:
        """Remove every field."""
        self._fields.clear()
        return self

    def build(self) -> Embed:
        embed = Embed(
            title=self._title,
            description=self._description,
            color=self._color,
            url=self._url,
            timestamp=self._timestamp,
        )

        if self._author:
            embed.set_author(**self._author)
        if self._thumbnail:
            embed.set_thumbnail(url=self._thumbnail)
        if self._image:
            embed.set_image(url=self._image)

        final_footer_text = self._footer.get("text") if self._footer else None
        footer_icon_url = self._footer.get("icon_url") if self._footer else None

        # Append the theme's branding only when the limits do not allow hiding it;
        # a caller permitted to hide it keeps its own footer untouched.
        if not self._limits.hide_branding and self._theme.footer:
            if final_footer_text:
                final_footer_text += f" | {self._theme.footer}"
            else:
                final_footer_text = self._theme.footer

        if final_footer_text:
            embed.set_footer(text=final_footer_text, icon_url=footer_icon_url)

        for field in self._fields:
            embed.add_field(**field)

        return embed
