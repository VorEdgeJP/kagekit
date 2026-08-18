"""The injection points — theme, wording and limits.

KageKit itself **imports nothing but discord.py and the standard library**. Anything
that belongs to the host application — branding, localised wording, per-plan caps —
comes through here. That invariant is what lets the same code serve one product and
ship as a standalone package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .tokens import DEFAULT_PALETTE, Palette


@dataclass(frozen=True)
class Labels:
    """Fixed wording the UI emits. The defaults are English and locale-neutral."""

    # Embed templates
    success_title: str = "Success"
    error_title: str = "Error"
    warning_title: str = "Warning"
    info_title: str = "Info"

    # State
    enabled: str = "Enabled"
    disabled: str = "Disabled"
    processing: str = "In progress"

    # Navigation (ActionBar / Pager)
    back: str = "Back"
    close: str = "Close"
    reload: str = "Reload"
    jump_title: str = "Go to page"
    jump_field: str = "Page number"
    jump_invalid: str = "Enter a number between 1 and {total}."
    page_format: str = "{current} / {total}"

    # Errors
    feature_disabled: str = "This feature is not available."
    field_limit: str = "You can only add {max} fields."


@dataclass(frozen=True)
class Emojis:
    """Emoji the UI emits. Swappable for the same reason the wording is."""

    enabled: str = "\N{LARGE GREEN CIRCLE}"
    disabled: str = "\N{MEDIUM WHITE CIRCLE}"
    processing: str = "\N{LARGE BLUE CIRCLE}"

    back: str = "\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}"
    close: str = "\N{HEAVY MULTIPLICATION X}"
    reload: str = "\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}"

    first: str = "\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}"
    prev: str = "\N{BLACK LEFT-POINTING TRIANGLE}"
    next: str = "\N{BLACK RIGHT-POINTING TRIANGLE}"
    last: str = "\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}"


@dataclass(frozen=True)
class Limits:
    """Caps the UI honours. Unlimited by default, so no billing concept leaks in.

    A host with tiers maps its own limit lookup into this shape.
    """

    #: Whether the title may be turned into a hyperlink.
    embed_url_enabled: bool = True
    #: Maximum embed fields. ``None`` means unlimited.
    max_embed_fields: Optional[int] = None
    #: Whether the branding footer may be hidden (True = not appended).
    hide_branding: bool = True


UNLIMITED = Limits()


@dataclass(frozen=True)
class Theme:
    """Palette, wording and branding, bundled."""

    palette: Palette = DEFAULT_PALETTE
    labels: Labels = field(default_factory=Labels)
    emojis: Emojis = field(default_factory=Emojis)
    #: Branding appended to the end of every message; ``None`` appends nothing.
    #: Rendered as subtext (``-# ``) in Components V2 and as the footer in an embed.
    footer: Optional[str] = None

    def status(self, enabled: bool) -> str:
        """The shared on/off wording (``🟢 Enabled`` / ``⚪ Disabled``).

        Panels drift apart when each one picks its own emoji and phrasing, so state
        display goes through here.
        """
        if enabled:
            return f"{self.emojis.enabled} {self.labels.enabled}"
        return f"{self.emojis.disabled} {self.labels.disabled}"


DEFAULT_THEME = Theme()
