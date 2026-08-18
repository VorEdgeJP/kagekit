# KageKit

A declarative UI layer for [discord.py](https://github.com/Rapptz/discord.py) Components V2.

Components V2 lets you build anything, which is the problem: every panel ends up
re-deciding where the tabs go, which red means "you cannot undo this", and whether a
sub-menu should stack a new ephemeral message. KageKit turns those decisions into
structure — you describe the panel, and the layout is not yours to get wrong.

```python
from kagekit import Action, ActionBar, Card, Page, Pager, SettingRow, Tab, TabBar, Text

await Page(
    tabs=TabBar(
        tabs=[Tab("Pending", "pending"), Tab("Done", "done")],
        active="pending",
        on_change=self.switch_tab,          # (interaction, value)
    ),
    body=[
        Card(title="🎫 Ticket settings", intent="brand", children=[
            SettingRow("Category", category.name, emoji="📂",
                       action="Change", on_click=self.edit_category),
            SettingRow("Notify", channel.mention, emoji="🔔",
                       action="Change", on_click=self.edit_notify),
        ]),
        Card(title="Delete every ticket", intent="danger", children=[
            Text("This cannot be undone."),
        ]),
    ],
    pager=Pager(current=3, total=12, on_change=self.goto),   # (interaction, page)
    actions=ActionBar(on_reload=self.reload, on_back=self.back),
).edit(interaction)
```

## Install

```bash
pip install discord-kagekit
```

Requires Python 3.11+ and discord.py 2.7+. KageKit imports nothing but discord.py and
the standard library.

## The layout contract

```text
┌ TabBar ─────────────  outside the container, at the very top
│  [Pending] [Running] [Done]
├ Card ───────────────  Container(accent = intent)
│  ## Heading / setting rows
├ Card ───────────────  a different subject gets its own card
├ Pager ──────────────  ⏮  ◀  [ 3 / 12 ]  ▶  ⏭
└ ActionBar ──────────  🔄 Reload   ◀️ Back   ✖️ Close   outside, at the very bottom
```

- **Section switches** (pending / running / done) change *what the page is showing*, so
  they sit above the cards, not inside one.
- **Reload / Back / Close** act on the message as a whole, so they sit at the bottom,
  outside every card.
- **Paging** is its own row: the center button reads `current / total` and opens a modal
  to jump; the outer buttons step one page and jump to either end. It is separate from
  the ActionBar because it moves through the contents *inside* a card.
- **Content that is genuinely different gets its own card**, with the accent carrying
  the intent.
- Operations edit the **same message in place**. Stacking a new ephemeral per step is
  not something the layer offers.

### What it guarantees

- More than five tabs become a select instead of overflowing the five-button row.
- The active tab renders primary and unclickable; a control with no handler renders
  disabled rather than as a button that does nothing.
- A `Text` after a `SettingRow` does not leak into that row's `Section` — a recurring
  bug when panels are hand-built.
- The budget is checked before sending: exceeding Discord's 10 top-level slots or 40
  components raises `LimitError` telling you what to cut, instead of an opaque API
  rejection.

## Cards

| Child | What it is |
| --- | --- |
| `SettingRow` | one setting: `**{emoji} {label}**: {value}` plus a button on the right |
| `Text` | plain text (write `## ` yourself for a heading) |
| `Heading` | a sub-heading; `thumbnail=` hangs an image off it |
| `Divider` | a separator line |
| `Actions([Action(...)])` | a button row for that card's subject; wraps past five |
| `Select` | `string` / `role` / `channel` / `user` / `mentionable`; always its own row |
| `Control` | a raw `discord.ui.Item`, for persistent views the above can't express |

## Theming

KageKit ships neutral: English labels, no branding, no limits. Everything
product-specific is injected.

```python
from kagekit import ComponentBuilder, Labels, Limits, Theme

theme = Theme(
    labels=Labels(back="戻る", close="閉じる", reload="更新"),
    footer="Made with example.com",     # appended as subtext on the last card
)
cb = ComponentBuilder(theme=theme)
```

`Theme.status(enabled)` returns the shared `🟢 Enabled` / `⚪ Disabled` wording, and
`state_intent(enabled)` returns the matching card intent, so state reads the same in
text and in colour across every panel.

### Palette

Discord's stock colours are highly saturated; four cards in a row become a stack of
neon bars. The default palette keeps the hue and drops the saturation to a value that
stays legible on both Discord themes.

| Token | Value | Meaning |
| --- | --- | --- |
| `brand` | `#6F63E0` | ordinary panels, the primary action |
| `success` | `#3F9E72` | done, enabled |
| `warning` | `#C79141` | recoverable warning |
| `danger` | `#C2504F` | destructive and irreversible |
| `info` | `#4A87A8` | informational, in progress |
| `neutral` | `#6E7480` | neutral, disabled |

`DISCORD_CLASSIC` keeps the old stock values if you want them back.

## The low layer

`ComponentBuilder` is the method-chaining builder the declarative layer is built on. It
is public: reach for it when you need something `Page` does not model (a persistent
`custom_id` view, a bespoke message), and use `render_card(cb, card)` to drop a
declarative card into a hand-built view.

## Limits

Discord caps a message at 10 top-level components and 40 in total, and an action row at
5 buttons. A card that exists only to hold a heading costs about 3 components — worth
knowing before you split one panel into six cards.

## Contributing

This repository is generated from the bot it lives in — see
[CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

Writing panels with an AI agent? [AGENTS.md](AGENTS.md) is the contract in one page.

## License

MIT
