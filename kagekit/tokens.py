"""Design tokens.

An accent colour surfaces as the 4px bar down the left of a Container, as a button
fill, and as an embed colour. **Never write a hex literal at a call site** — this
module is the single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """intent -> colour, each an ``0xRRGGBB`` int."""

    brand: int
    success: int
    warning: int
    danger: int
    info: int
    neutral: int


#: The default. Each colour keeps its hue but drops to a mid-luminance, low-saturation
#: value so the accent bar stays legible against both Discord themes (#313338 and
#: #FFFFFF). Contrast on the dark theme is what decided it.
MUTED_JEWEL = Palette(
    brand=0x6F63E0,
    success=0x3F9E72,
    warning=0xC79141,
    danger=0xC2504F,
    info=0x4A87A8,
    neutral=0x6E7480,
)

#: The runner-up: darker and cooler. It tightens up on the light theme, but on the dark
#: one the bar sinks into the background and the intent stops reading.
DEEP_SLATE = Palette(
    brand=0x5C57B8,
    success=0x35815F,
    warning=0xA87A38,
    danger=0xA34A4C,
    info=0x3F6E8A,
    neutral=0x5E6470,
)

#: Discord's stock colours. Highly saturated — a stack of cards turns into neon bars —
#: kept for comparison and for anyone migrating.
DISCORD_CLASSIC = Palette(
    brand=0x5865F2,
    success=0x57F287,
    warning=0xFEE75C,
    danger=0xED4245,
    info=0x3498DB,
    neutral=0x99AAB5,
)

DEFAULT_PALETTE = MUTED_JEWEL
