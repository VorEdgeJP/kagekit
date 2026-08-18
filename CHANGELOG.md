# Changelog

## 0.1.0 — unreleased

First public release. Extracted from the BotShade bot, where it renders every
Components V2 panel (19 surfaces).

- `Page` / `Card` / `TabBar` / `Pager` / `ActionBar` — the declarative layer that
  enforces the layout contract.
- Card children: `SettingRow`, `Text`, `Heading`, `Divider`, `Actions` / `Action`,
  `Select`, `Control`.
- `ComponentBuilder` — the Components V2 builder underneath, public for the cases the
  declarative layer does not model, plus `render_card()` to mix the two.
- `Theme` / `Labels` / `Emojis` / `Limits` — every product-specific string, limit and
  colour is injected; the defaults are neutral English with no branding.
- `Palette` with `MUTED_JEWEL` (default), `DEEP_SLATE` and `DISCORD_CLASSIC`.
- `EmbedBuilder` for the contexts that cannot use Components V2.
- Budget checks before send: `LimitError` naming what to cut instead of an API
  rejection.
