# KageKit for coding agents

You are writing a Discord panel with KageKit. Describe the panel; the library decides
where things go. If you find yourself reaching for a parameter that moves the tabs or
the back button somewhere else, it does not exist — that is the point.

Read this before writing the first `Page(...)`.

## The contract

```text
┌ TabBar ─────────────  outside the container, at the very top
│  [Pending] [Running] [Done]
├ Card ───────────────  Container(accent = intent)
│  ## Heading / setting rows
├ Card ───────────────  a different subject gets its own card
├ Pager ──────────────  ⏮  ◀  [ 3 / 12 ]  ▶  ⏭
└ ActionBar ──────────  🔄 Reload   ◀️ Back   ✖️ Close   outside, at the very bottom
```

| Slot | What belongs there | What does not |
| --- | --- | --- |
| `tabs` | switching *what the page shows* (pending / running / done) | anything that mutates data |
| `body` | cards — one per subject | message-wide controls |
| `pager` | moving through the contents *inside* a card | anything that acts on the message |
| `actions` | reload / back / close, plus `extra=[Action(...)]` for a docs link | per-card operations |

Operations edit the **same message in place** (`await page.edit(interaction)`). Do not
send a new ephemeral per step; there is no API for stacking panels because stacked
panels are the thing this library exists to stop.

## Choosing a piece

| You want | Use |
| --- | --- |
| one setting: label, current value, a button to change it | `SettingRow(...)` |
| a heading inside a card | `Heading("...")` — `thumbnail=` for an image, `raw=True` to keep your own formatting |
| free text, a warning line, a `-#` subtext | `Text("...")` |
| buttons that act on *this card's* subject | `Actions([Action(...), ...])` — wraps past five |
| a dropdown | `Select(kind="string"/"role"/"channel"/"user"/"mentionable", ...)` |
| a separator | `Divider()` |
| a persistent `custom_id` view, or anything above can't express | `Control(item=<discord.ui.Item>)` |
| state shown the same way everywhere | `theme.status(enabled)` + `intent=state_intent(enabled)` |

## Handler signatures

```python
on_click   = async def (interaction) -> None                 # Action, SettingRow
on_change  = async def (interaction, values: list) -> None   # Select
on_change  = async def (interaction, value: str) -> None     # TabBar
on_change  = async def (interaction, page: int) -> None      # Pager (1-based)
```

`Page.build()` returns a `discord.ui.LayoutView`. `await page.send(interaction)` for the
first message, `await page.edit(interaction)` for every step after — both handle the
Components V2 restriction that a V2 message cannot carry `content` or `embeds`.

## Rules that are easy to get wrong

- **Never write a hex colour.** Use `intent="brand" | "success" | "warning" | "danger" |
  "info" | "neutral"`. `accent=0x…` exists only as a migration escape hatch and for a
  genuine brand colour.
- **A `Text` right after a `SettingRow` would leak into that row's Section** if you built
  it by hand. KageKit closes the section for you — but if you drop to
  `ComponentBuilder`, call `end_section()` first.
- **A `Select` always occupies its own row.** Do not try to put one next to buttons.
- **More than five tabs becomes a select automatically.** Do not hand-roll that.
- **A control with no handler renders disabled.** Do not add a button you have not wired
  up and expect it to look active.
- **Read your own writes.** After a mutation, rebuild the panel from the primary
  database, not a replica. A lagging replica redraws the *old* state and the button looks
  broken.

## The budget — count before you split

Discord allows **10 top-level components**, **40 components in total**, and **5 buttons
per row**. KageKit raises `LimitError` before sending, naming what to cut, but you should
plan for it:

| Piece | Roughly costs |
| --- | --- |
| a card | 1 + its children |
| a `SettingRow` with a button | 3 (separator + section + button) — 2 with `separator=False` |
| a `Text` / `Heading` | 1 |
| `Actions` / `Select` | 1 for the row + 1 per control |
| TabBar / Pager / ActionBar | 1 top-level slot each (Pager fills its row exactly) |

**A card that exists only to hold a heading costs about 3.** When a panel gets tight,
merge the header into the first real card before you drop content.

## Testing a panel

Assert on the payload, not on a screenshot. This is the house style:

```python
payload = page.build().to_components()

assert [c["type"] for c in payload] == [1, 17, 1]    # TabBar / Card / ActionBar
assert payload[0]["components"][0]["disabled"] is True        # active tab
assert payload[-1]["components"][0]["label"] == "Reload"
assert _count_components(payload) <= 40                       # budget
```

Component type numbers: `1` action row, `2` button, `3` string select, `5` user select,
`6` role select, `8` channel select, `9` section, `10` text display, `14` separator,
`17` container.

## Anti-patterns

```python
# ✗ stacking a new ephemeral for a sub-menu
await interaction.response.send_message(view=sub_view, ephemeral=True)
# ✓ replace the same message
await Page(body=[card], actions=ActionBar(on_back=back)).edit(interaction)

# ✗ a hex literal
Card(accent=0xED4245, ...)
# ✓ say what it means
Card(intent="danger", ...)

# ✗ putting back/close inside a card
Card(children=[..., Actions([Action("Back", on_click=back)])])
# ✓ the bottom bar is where message-wide controls live
Page(body=[card], actions=ActionBar(on_back=back))

# ✗ a heading-only card, then wondering why the budget blew up
Page(body=[Card(title="Settings"), Card(children=rows)])
# ✓ one card
Page(body=[Card(title="Settings", children=rows)])
```
