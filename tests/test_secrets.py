from codex_team.secrets import MemorySecretStore,WindowsSecretStore


def test_secret_abstraction_never_returns_full_key_in_status():
    store = MemorySecretStore()
    assert not store.status()['configured']
    store.save('sk-test-not-real-1234')
    assert store.read() == 'sk-test-not-real-1234'
    assert store.status() == {'configured':True,'key_hint':'••••1234'}
    store.remove()
    assert store.read() is None


def test_credentials_are_namespaced_per_data_root(tmp_path):
    assert WindowsSecretStore(tmp_path/'installed').target != WindowsSecretStore(tmp_path/'portable').target
    assert WindowsSecretStore(tmp_path/'installed').target == WindowsSecretStore(tmp_path/'installed').target
