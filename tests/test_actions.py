import threading
import time
import pytest
from codex_team.actions import ActionCenter, COMMAND, PERMISSIONS, INPUT, describe_error
from codex_team.storage import Store


@pytest.fixture
def center(tmp_path):
    store = Store(tmp_path / 'test.sqlite3')
    center = ActionCenter(store)
    yield center
    center.close()
    store.close()


def pending(center, method, params):
    response = []
    thread = threading.Thread(target=lambda: response.append(center.request('run_test', 'developer', method, params, timeout=3)))
    thread.start()
    deadline = time.monotonic() + 2
    while not center.store.actions(status='pending'):
        assert time.monotonic() < deadline
        time.sleep(.01)
    return center.store.actions(status='pending')[0], response, thread


def test_permission_requires_explicit_scope_confirmation_and_real_native_response(center):
    card, response, thread = pending(center, COMMAND, {'command': 'python -m pip install pytest', 'cwd': 'C:/project'})
    with pytest.raises(ValueError, match='подтвердите'):
        center.resolve(card['id'], 'allow_once')
    assert thread.is_alive()
    center.resolve(card['id'], 'allow_once', confirmed=True)
    thread.join(2)
    assert response == [{'decision': 'accept'}]
    assert center.store.action(card['id'])['decision'] == 'allow_once'
    with pytest.raises(ValueError, match='больше не'):
        center.resolve(card['id'], 'allow_run', confirmed=True)


def test_native_permission_grants_only_requested_subset_and_session(center):
    permissions = {'fileSystem': {'read': ['C:/project/tool']}, 'network': None}
    card, response, thread = pending(center, PERMISSIONS, {'permissions': permissions})
    center.resolve(card['id'], 'allow_run', confirmed=True)
    thread.join(2)
    assert response == [{'permissions': permissions, 'scope': 'session'}]


def test_sdk_available_decisions_are_authoritative(center):
    card, response, thread = pending(center, COMMAND, {'availableDecisions': ['decline', 'cancel']})
    assert 'allow_once' not in card['allowed_decisions']
    with pytest.raises(ValueError, match='не поддерживает'):
        center.resolve(card['id'], 'allow_once', confirmed=True)
    center.resolve(card['id'], 'deny')
    thread.join(2)
    assert response == [{'decision': 'decline'}]


def test_typed_input_answers_not_persisted(center):
    center.store.save_settings({'permission_policy':{'command_execution':'deny'}})
    card, response, thread = pending(center, INPUT, {'questions': [{'id': 'strategy', 'question': 'Which?', 'isSecret': False}]})
    with pytest.raises(ValueError, match='Неизвестный'):
        center.resolve(card['id'], 'answer', {'unrelated': ['private answer']})
    center.resolve(card['id'], 'answer', {'strategy': ['private answer']})
    thread.join(2)
    assert response == [{'answers': {'strategy': {'answers': ['private answer']}}}]
    assert 'private answer' not in str(center.store.actions())


def test_cancel_releases_blocked_sdk_reader_before_interrupt(center):
    card, response, thread = pending(center, COMMAND, {'command': 'test'})
    center.cancel_run('run_test')
    thread.join(2)
    assert not thread.is_alive()
    assert response == [{'decision': 'cancel'}]


def test_recovery_cannot_replay_stale_approval(center):
    center.store.save_action({'id':'old','run_id':'run_test','status':'pending','details':{'apiKey':'private'}})
    center.store.recover()
    assert center.store.action('old')['status'] == 'expired'
    assert 'private' not in str(center.store.action('old'))
    with pytest.raises(ValueError, match='больше не'):
        center.resolve('old', 'allow_once', confirmed=True)


def test_redacted_command_cannot_hide_destructive_suffix_and_receive_grant(center):
    response = center.request('run_test','developer',COMMAND,{'command':'$env:API_KEY="placeholder"; Remove-Item -LiteralPath project-data -Recurse -Force'})
    card = center.store.actions()[0]
    assert response == {'decision':'decline'}
    assert not card['sdk_supported']
    assert 'allow_once' not in card['allowed_decisions']
    assert 'скрыты секретные значения' in card['limitation']


def test_errors_classify_action_auth_and_recoverable_without_traceback():
    assert describe_error('AUTH_REQUIRED','expired')['category'] == 'AUTH_REQUIRED'
    assert describe_error('USER_DECISION_REQUIRED','choose')['category'] == 'USER_ACTION_REQUIRED'
    assert describe_error('FAILED','apiKey=private')['message'] == 'apiKey=[REDACTED]'
