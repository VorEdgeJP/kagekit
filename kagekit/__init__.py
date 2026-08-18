"""KageKit — a declarative UI layer over discord.py Components V2.

Layers:

* ``tokens`` / ``theme`` — palette, wording and limits; every injection point
* ``page``   — the declarative layer (``Page`` / ``Card`` / ``TabBar`` / ``Pager`` / …)
* ``builder`` — the Components V2 primitives underneath (``ComponentBuilder``)
* ``embed``   — an embed builder for the contexts V2 cannot serve

**Invariant**: this package imports nothing but discord.py and the standard library.
Branding, localised wording and per-plan limits arrive as ``Theme`` and ``Limits``,
injected by the host application.

The layout contract, enforced by the declarative layer:

* section switches (pending / running / done) sit **outside the container, at the top**
* reload / back / close sit **outside the container, at the bottom**
* paging is its own row: ``current / total`` in the middle opening a jump modal, with
  step and jump-to-end buttons either side
* content that is genuinely different gets its own card
"""

from .builder import ComponentBuilder
from .embed import EmbedBuilder
from .errors import FeatureDisabledError, LimitError
from .page import (
    Action,
    ActionBar,
    Actions,
    Card,
    Control,
    Divider,
    Heading,
    Page,
    Pager,
    Select,
    SettingRow,
    Tab,
    TabBar,
    Text,
    render_card,
    state_intent,
)
from .theme import DEFAULT_THEME, UNLIMITED, Emojis, Labels, Limits, Theme
from .tokens import (
    DEEP_SLATE,
    DEFAULT_PALETTE,
    DISCORD_CLASSIC,
    MUTED_JEWEL,
    Palette,
)

__all__ = [
    "ComponentBuilder",
    "EmbedBuilder",
    "Page",
    "Card",
    "Text",
    "Divider",
    "Heading",
    "SettingRow",
    "Actions",
    "Action",
    "Select",
    "Control",
    "Tab",
    "TabBar",
    "Pager",
    "ActionBar",
    "state_intent",
    "render_card",
    "FeatureDisabledError",
    "LimitError",
    "Theme",
    "Labels",
    "Emojis",
    "Limits",
    "DEFAULT_THEME",
    "UNLIMITED",
    "Palette",
    "DEFAULT_PALETTE",
    "MUTED_JEWEL",
    "DEEP_SLATE",
    "DISCORD_CLASSIC",
]
