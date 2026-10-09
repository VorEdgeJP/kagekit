"""ViewStore hygiene when panels are edited in place."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from discord.ui.view import ViewStore

from kagekit import ActionBar, Card, ComponentBuilder, Page, SettingRow


async def noop(interaction, *args):
    return None


def _small_page(label: str = "A") -> Page:
    return Page(
        body=[
            Card(
                children=[
                    SettingRow("Key", label, action="Change", on_click=noop),
                ],
            )
        ],
        actions=ActionBar(on_close=noop),
    )


def _dispatch_view_count(store: ViewStore, message_id: int) -> tuple[int, int]:
    bucket = store._views.get(message_id, {})
    view_ids = {id(item.view) for item in bucket.values() if item.view is not None}
    return len(bucket), len(view_ids)


@pytest.mark.asyncio
async def test_edit_interaction_response_stops_previous_view():
    """Repeated Page edits must not accumulate views in discord.py's ViewStore."""
    message_id = 4242
    store = ViewStore(state=None)
    state = SimpleNamespace(
        prevent_view_updates_for=store.remove_message_tracking,
        store_view=store.add_view,
    )

    class _Message:
        id = message_id

    class _Response:
        async def edit_message(self, **kwargs):
            # Mirror InteractionResponse.edit_message view bookkeeping (2.7.x).
            view = kwargs.get("view")
            state.prevent_view_updates_for(message_id)
            if view and not view.is_finished() and view.is_dispatchable():
                state.store_view(view, message_id)

    interaction = SimpleNamespace(message=_Message(), _state=state, response=_Response())

    first = _small_page("0").build()
    store.add_view(first, message_id)

    for i in range(1, 51):
        await ComponentBuilder.edit_interaction_response(interaction, _small_page(str(i)).build())

    entries, views = _dispatch_view_count(store, message_id)
    assert views == 1
    assert entries == 2  # SettingRow button + ActionBar close


@pytest.mark.asyncio
async def test_edit_reuses_same_view_instance_without_stopping_it():
    """ComponentBuilder callers may pass the same LayoutView to edit again."""
    message_id = 9001
    store = ViewStore(state=None)
    state = SimpleNamespace(
        prevent_view_updates_for=store.remove_message_tracking,
        store_view=store.add_view,
    )

    class _Message:
        id = message_id

    class _Response:
        async def edit_message(self, **kwargs):
            view = kwargs.get("view")
            state.prevent_view_updates_for(message_id)
            if view and not view.is_finished() and view.is_dispatchable():
                state.store_view(view, message_id)

    interaction = SimpleNamespace(message=_Message(), _state=state, response=_Response())

    view = _small_page("same").build()
    store.add_view(view, message_id)

    await ComponentBuilder.edit_interaction_response(interaction, view)
    await ComponentBuilder.edit_interaction_response(interaction, view)

    assert not view.is_finished()
    entries, views = _dispatch_view_count(store, message_id)
    assert views == 1
    assert entries == 2


@pytest.mark.asyncio
async def test_edit_failure_restores_sync_when_same_view_not_stopped():
    message_id = 9002
    store = ViewStore(state=None)
    state = SimpleNamespace(
        prevent_view_updates_for=store.remove_message_tracking,
        store_view=store.add_view,
    )

    class _Message:
        id = message_id

    calls = {"n": 0}

    class _Response:
        async def edit_message(self, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("edit failed")
            view = kwargs.get("view")
            state.prevent_view_updates_for(message_id)
            if view and not view.is_finished() and view.is_dispatchable():
                state.store_view(view, message_id)

    interaction = SimpleNamespace(message=_Message(), _state=state, response=_Response())

    view = _small_page("x").build()
    store.add_view(view, message_id)

    with pytest.raises(RuntimeError, match="edit failed"):
        await ComponentBuilder.edit_interaction_response(interaction, view)

    assert store._synced_message_views.get(message_id) is view

    await ComponentBuilder.edit_interaction_response(interaction, view)
    entries, views = _dispatch_view_count(store, message_id)
    assert views == 1
    assert entries == 2
