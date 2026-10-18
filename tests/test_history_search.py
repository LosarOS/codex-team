"""History search must use the user's literal Unicode text."""
import pytest
from codex_team.storage import Store


@pytest.mark.parametrize('query', ['АВТОРИЗАЦИЯ', 'авторизация', 'ПРОЕКТ', 'strasse'])
def test_unicode_history_search_preserves_saved_data(tmp_path, query):
    store = Store(tmp_path / 'state.db')
    run = {'id': 'unicode', 'task': 'Авторизация Straße', 'workspace': 'C:\\Проект', 'calls': 0}
    try:
        store.save_run(run)
        page = store.run_page(q=query)
        assert page['total'] == 1
        assert page['items'][0]['id'] == 'unicode'
        assert store.run('unicode') == run
    finally:
        store.close()


def test_literal_wildcards_and_pagination_are_preserved(tmp_path):
    store = Store(tmp_path / 'state.db')
    try:
        for i in range(3):
            store.save_run({'id': str(i), 'task': f'ТЕСТ %_ {i}', 'workspace': '/repo'})
        store.save_run({'id': 'other', 'task': 'ТЕСТ plain', 'workspace': '/repo'})
        page = store.run_page(q='%_', offset=1, limit=1)
        assert page['total'] == 3
        assert page['items'][0]['id'] == '1'
        assert store.run_page(q="' OR 1=1 --")['total'] == 0
    finally:
        store.close()
