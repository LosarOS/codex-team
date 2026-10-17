"""Appearance preferences survive partial writes and app/store restarts."""
import pytest

from codex_team.settings import Settings
from codex_team.storage import Store
from test_server import local_app


@pytest.mark.parametrize('theme', [
    'system', 'light', 'dark', 'purple-neon', 'dark-fantasy',
    'obsidian-violet', 'neon-blue', 'emerald-tech', 'crimson-night',
])
def test_all_current_and_legacy_themes_round_trip(local_app, theme):
    client, _, _, db, _ = local_app
    assert client.post('/api/settings', json={'theme': theme}).status_code == 200
    assert client.post('/api/settings', json={'language': 'en'}).status_code == 200
    assert client.get('/api/settings').json()['theme'] == theme
    assert client.get('/api/status').json()['settings']['language'] == 'en'
    # A separate SQLite connection demonstrates persistence rather than frontend cache.
    reopened = Store(db.path)
    try:
        assert reopened.settings()['theme'] == theme
        assert reopened.settings()['language'] == 'en'
    finally:
        reopened.close()


def test_first_launch_status_and_settings_share_appearance_defaults(local_app):
    client, _, _, db, _ = local_app
    preferences = client.get('/api/settings').json()
    assert preferences['theme'] == 'obsidian-violet'
    assert preferences['language'] == 'ru'
    assert client.get('/api/status').json()['settings'] == preferences
    assert db.settings() == {}  # Reading defaults does not migrate/overwrite user data.


@pytest.mark.parametrize('patch', [
    {'language': 'de'}, {'language': None}, {'theme': 'unsupported'},
    {'theme': '../../private'}, {'language': '<script>'},
])
def test_invalid_appearance_preferences_are_atomic(local_app, patch):
    client, _, _, db, _ = local_app
    db.save_settings({'language': 'ru', 'theme': 'dark-fantasy'})
    before = db.settings()
    assert client.post('/api/settings', json=patch).status_code == 422
    assert db.settings() == before


def test_partial_preferences_keep_explicit_language_and_legacy_theme(local_app):
    client, _, _, db, _ = local_app
    db.save_settings({'theme': 'system', 'language': 'en', 'model': 'existing-model'})
    assert client.post('/api/settings', json={'max_iterations': 4}).status_code == 200
    saved = client.get('/api/status').json()['settings']
    assert saved['theme'] == 'system' and saved['language'] == 'en'
    assert saved['model'] == 'existing-model'
    assert Settings().language == 'ru'
