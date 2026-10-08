"""Reproduce discord.py ViewStore behavior on repeated message edits (no HTTP).

Simulates InteractionResponse.edit_message view bookkeeping:
  prevent_view_updates_for(message_id)  -> remove_message_tracking only
  store_view(view, message_id)           -> add_view
"""

from __future__ import annotations

import gc
import tracemalloc
from unittest.mock import MagicMock

from discord.ui.view import ViewStore

from kagekit import ActionBar, Card, Page, SettingRow, Tab, TabBar


async def noop(_interaction, *_args):
    return None


def sample_page() -> Page:
    return Page(
        tabs=TabBar(
            tabs=[Tab("Pending", "pending"), Tab("Done", "done")],
            active="pending",
            on_change=noop,
        ),
        body=[
            Card(
                title="Settings",
                intent="brand",
                children=[
                    SettingRow("Category", "Support", emoji="📂", action="Change", on_click=noop),
                ],
            ),
        ],
        actions=ActionBar(on_reload=noop, on_back=noop, on_close=noop),
    )


def dispatch_map_stats(store: ViewStore, message_id: int) -> dict:
    dispatch = store._views.get(message_id, {})
    view_ids: set[int] = set()
    for item in dispatch.values():
        if item.view is not None:
            view_ids.add(id(item.view))
    synced = store._synced_message_views.get(message_id)
    return {
        "dispatch_entries": len(dispatch),
        "distinct_view_objects": len(view_ids),
        "synced_message_views": 1 if synced is not None else 0,
        "synced_view_id": id(synced) if synced is not None else None,
    }


def simulate_edit_naive(store: ViewStore, message_id: int, view) -> None:
    """Matches discord.py InteractionResponse.edit_message (2.7.1) view handling."""
    store.remove_message_tracking(message_id)
    if view and not view.is_finished() and view.is_dispatchable():
        store.add_view(view, message_id)


def simulate_edit_stop_previous(store: ViewStore, message_id: int, view) -> None:
    old = store.remove_message_tracking(message_id)
    if old is not None:
        old.stop()
    if view and not view.is_finished() and view.is_dispatchable():
        store.add_view(view, message_id)


def collect_custom_ids(view) -> list[str]:
    ids: list[str] = []
    for item in view.walk_children():
        if item.is_dispatchable():
            ids.append(item.custom_id)  # type: ignore[arg-type]
    return ids


def run_series(simulate_edit, n: int = 100) -> dict:
    store = ViewStore(MagicMock())
    message_id = 9_007_199_254_740_991
    tracemalloc.start()
    gc.collect()
    snap0 = tracemalloc.take_snapshot()

    last_custom_ids: list[str] | None = None
    for _ in range(n):
        view = sample_page().build()
        cids = collect_custom_ids(view)
        if last_custom_ids is not None:
            assert cids != last_custom_ids, "expected new random custom_ids each build"
        last_custom_ids = cids
        simulate_edit(store, message_id, view)

    snap1 = tracemalloc.take_snapshot()
    stats = dispatch_map_stats(store, message_id)
    top = snap1.compare_to(snap0, "lineno")
    traced_delta = sum(s.size_diff for s in top[:50])
    tracemalloc.stop()
    stats["tracemalloc_top50_delta_bytes"] = traced_delta
    stats["edits"] = n
    stats["buttons_per_view"] = len(last_custom_ids or [])
    return stats


def main() -> None:
    n = 100
    naive = run_series(simulate_edit_naive, n)
    fixed = run_series(simulate_edit_stop_previous, n)

    print("=== KageKit Page.build() per edit (typical panel) ===")
    print(f"buttons/selects per view (dispatchable): {naive['buttons_per_view']}")
    print()
    print("=== Naive edit (discord.py edit_message semantics) ===")
    for k, v in naive.items():
        print(f"  {k}: {v}")
    print()
    print("=== Control: stop() previous view before store_view ===")
    for k, v in fixed.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
