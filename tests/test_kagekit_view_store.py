"""ViewStore hygiene when panels are edited in place.

These go through discord.py's real ``InteractionResponse.edit_message`` with only the
HTTP call mocked, so a change in discord.py's view bookkeeping shows up here.
"""

from __future__ import annotations

from unittest import mock

import discord
import pytest
from discord.webhook import async_ as webhook_async

from kagekit import Action, ActionBar, Actions, Card, ComponentBuilder, Page, SettingRow

MESSAGE_ID = 4242


async def noop(interaction, *args):
    return None


def _small_page(label: str = "A", *, fixed_custom_id: str | None = None) -> Page:
    children = [SettingRow("Key", label, action="Change", on_click=noop)]
    if fixed_custom_id is not None:
        children.append(Actions([Action("Fixed", on_click=noop, custom_id=fixed_custom_id)]))
    return Page(body=[Card(children=children)], actions=ActionBar(on_close=noop))


def _interaction(state, n: int) -> discord.Interaction:
    user = {"id": "555", "username": "u", "discriminator": "0", "avatar": None}
    message = {
        "id": str(MESSAGE_ID), "channel_id": "222", "type": 0, "content": "",
        "author": {"id": "333", "username": "bot", "discriminator": "0", "avatar": None},
        "attachments": [], "embeds": [], "mentions": [], "mention_roles": [],
        "pinned": False, "mention_everyone": False, "tts": False,
        "timestamp": "2026-01-01T00:00:00+00:00", "edited_timestamp": None,
        "flags": 1 << 15, "components": [],
    }  # fmt: skip
    data = {
        "id": str(900000 + n), "application_id": "444", "type": 3, "token": "tok",
        "version": 1, "channel_id": "222", "message": message, "user": user,
        "data": {"component_type": 2, "custom_id": "x"},
        "locale": "en-US", "app_permissions": "0", "entitlements": [],
        "authorizing_integration_owners": {}, "attachment_size_limit": 0,
    }  # fmt: skip
    return discord.Interaction(data=data, state=state)


@pytest.fixture
async def client():
    client = discord.Client(intents=discord.Intents.none())
    yield client
    await client.close()


@pytest.fixture
def http_ok():
    async def respond(self, *args, **kwargs):
        return {"interaction": {"id": "1", "type": 3}}

    with mock.patch.object(
        webhook_async.AsyncWebhookAdapter, "create_interaction_response", respond
    ):
        yield


def _dispatch(store) -> dict:
    return store._views.get(MESSAGE_ID, {})


def _routable(store, view: discord.ui.LayoutView) -> bool:
    keys = [
        (item.type.value, item.custom_id) for item in view.walk_children() if item.is_dispatchable()
    ]
    return all(_dispatch(store).get(key) is not None for key in keys)


async def test_repeated_edits_do_not_accumulate_views(client, http_ok):
    state = client._connection
    store = state._view_store

    for i in range(1, 51):
        view = _small_page(str(i)).build()
        await ComponentBuilder.edit_interaction_response(_interaction(state, i), view)

    bucket = _dispatch(store)
    assert {id(item.view) for item in bucket.values()} == {id(view)}
    assert len(bucket) == 2  # SettingRow button + ActionBar close
    assert store._synced_message_views[MESSAGE_ID] is view
    assert _routable(store, view)


async def test_reediting_with_the_same_view_keeps_it_alive(client, http_ok):
    state = client._connection
    store = state._view_store
    view = _small_page("same").build()

    await ComponentBuilder.edit_interaction_response(_interaction(state, 1), view)
    await ComponentBuilder.edit_interaction_response(_interaction(state, 2), view)

    assert not view.is_finished()
    assert store._synced_message_views[MESSAGE_ID] is view
    assert _routable(store, view)


async def test_failed_edit_leaves_the_old_buttons_working(client, http_ok):
    state = client._connection
    store = state._view_store
    old = _small_page("old").build()
    await ComponentBuilder.edit_interaction_response(_interaction(state, 1), old)

    async def fail(self, *args, **kwargs):
        raise RuntimeError("edit failed")

    with mock.patch.object(webhook_async.AsyncWebhookAdapter, "create_interaction_response", fail):
        with pytest.raises(RuntimeError, match="edit failed"):
            await ComponentBuilder.edit_interaction_response(
                _interaction(state, 2), _small_page("new").build()
            )

    assert not old.is_finished()
    assert store._synced_message_views[MESSAGE_ID] is old
    assert _routable(store, old)


async def test_a_custom_id_shared_across_builds_stays_routable(client, http_ok):
    # Stopping the old view removes its keys; a fixed custom_id is a key the new view
    # shares, so it must be routed to the new view afterwards, not dropped.
    state = client._connection
    store = state._view_store
    old = _small_page("old", fixed_custom_id="panel:fixed").build()
    new = _small_page("new", fixed_custom_id="panel:fixed").build()

    await ComponentBuilder.edit_interaction_response(_interaction(state, 1), old)
    await ComponentBuilder.edit_interaction_response(_interaction(state, 2), new)

    assert old.is_finished()
    assert _routable(store, new)
    assert _dispatch(store)[(2, "panel:fixed")].view is new
