"""Russian presentation must not change permission/notification protocol values."""
import pytest
from codex_team.actions import describe_error, role_title
from codex_team.desktop import STARTUP_HTML
from test_server import local_app


@pytest.mark.parametrize('code,category', [
    ('AUTH_REQUIRED', 'AUTH_REQUIRED'),
    ('USER_DECISION_REQUIRED', 'USER_ACTION_REQUIRED'),
    ('PERMISSION_REQUIRED', 'PERMISSION_REQUIRED'),
    ('CONFIGURATION_REQUIRED', 'CONFIGURATION_REQUIRED'),
    ('USAGE_LIMIT', 'USER_ACTION_REQUIRED'),
    ('INTERRUPTED', 'RECOVERABLE_ERROR'),
    ('FAILED', 'RECOVERABLE_ERROR'),
])
def test_russian_error_presentation_keeps_protocol_category(code, category):
    error = describe_error(code, 'technical diagnostic')
    assert error['category'] == category
    assert any('А' <= char <= 'я' for char in error['title'])
    assert any('А' <= char <= 'я' for char in error['remedy'])
    assert error['message'] == 'technical diagnostic'


def test_custom_role_and_startup_shell_remain_usable():
    assert role_title('developer') == 'Разработчик'
    assert role_title('my-custom-agent') == 'my-custom-agent'
    assert 'lang="ru"' in STARTUP_HTML
    assert '>Повторить</button>' in STARTUP_HTML
    assert '>Открыть журналы</button>' in STARTUP_HTML


def test_russian_validation_and_access_errors_do_not_echo_input(local_app):
    client, *_ = local_app
    response = client.post('/api/runs', json={'workspace': None, 'task': 'secret-input-value'})
    assert response.status_code == 422
    assert response.json()['detail'] == 'Проверьте поля ввода.'
    issue=response.json()['validation_errors'][0]
    assert issue['loc'] == ['body', 'workspace']
    assert issue['type'] == 'string_type'
    assert 'input' not in issue
    assert 'secret-input-value' not in response.text
    denied = client.post('/api/settings', json={}, headers={'origin': 'https://evil.invalid'})
    assert denied.status_code == 403
    assert 'запрещены' in denied.json()['detail']
    assert client.get('/api/runs/does-not-exist').json()['detail'] == 'Запрошенный элемент не найден.'
