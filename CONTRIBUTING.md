# Contributing to KageKit

Thanks for looking. A few things are unusual about this repository, so please read the
first section before opening a pull request.

## This repository is generated

KageKit lives inside the [BotShade](https://botshade.com) bot, where it renders every
settings panel. That copy is the source of truth; **this repository is produced from it
by a script** and force-refreshed when the upstream package changes.

That means:

- **Pull requests that edit `kagekit/` here cannot be merged as-is.** They would be
  overwritten by the next export. Open the issue or PR anyway — describe the change and
  it will be applied upstream and land here on the next refresh, with credit.
- Changes to `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, the workflows and the packaging
  metadata are also carried in the upstream repository (under `packaging/kagekit/`), so
  the same applies.
- Issues are the best entry point. A failing snippet is worth more than a patch here.

If this friction ever costs more than it saves, the layout will change. For now it keeps
one implementation rather than two that drift.

## Setting up

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
mypy kagekit
```

Python 3.11+ and discord.py 2.7+. There are no other dependencies, and that is a rule
rather than a coincidence — see below.

## The invariants

Three properties are load-bearing. A change that breaks one of them will be sent back.

**1. KageKit imports nothing but discord.py and the standard library.**
`tests/test_kagekit_foundation.py::TestOssInvariant` walks the AST of every module and
fails on a first-party import. Product-specific strings, limits and colours arrive
through `Theme` and `Limits`; they are never hardcoded.

**2. The defaults are neutral.** English labels, no branding, no limits. Anything that
looks like someone's product is injected by that someone.

**3. The layout contract is not configurable.** Tabs go outside at the top, reload/back/
close go outside at the bottom, the pager is its own row, different subjects get
different cards. There is deliberately no parameter to move them; a request to add one
is a request to remove the reason the library exists.

## What a good change looks like

- **Tests assert on the payload.** Build the view, call `to_components()`, and assert on
  the structure — component types, order, disabled flags, accent colours. Screenshots and
  live Discord calls are not part of the suite; the whole suite runs offline in under a
  second.
- **Comments explain the why.** The codebase is full of notes like "a select must own its
  row" or "a heading-only card costs about 3 components". Those are the expensive
  knowledge; keep adding them.
- **Discord's limits are treated as real.** 10 top-level components, 40 in total, 5
  buttons per row. If your change makes a panel likely to cross one, make the failure
  loud (`LimitError`) rather than letting the API reject it.
- **Japanese or English are both fine in issues.** Code comments in this package are
  English; the upstream bot's are Japanese.

## Releasing

Tags on `main` matching `v*` trigger `.github/workflows/publish.yml`, which builds and
publishes to PyPI through a Trusted Publisher (OIDC — there is no API token). The version
lives in `pyproject.toml` and must match the tag.

## License

By contributing you agree that your contribution is licensed under the MIT License, the
same as the rest of the project.
