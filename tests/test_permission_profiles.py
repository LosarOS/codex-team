import pytest

from codex_team.permission_profiles import PermissionProfileError, requested_capabilities, validate_permission_profile


def test_exact_official_profile_preserved_without_shared_mutation(tmp_path):
    profile = {"fileSystem": {"read": [str(tmp_path / "tool")], "write": None, "globScanMaxDepth": 16,
        "entries": [{"access": "read", "path": {"type": "path", "path": str(tmp_path / "data")}}]}, "network": {"enabled": False}}
    result = validate_permission_profile(profile)
    assert result == profile
    result["fileSystem"]["read"].append("changed")
    assert result != profile
    assert requested_capabilities(profile) == {"write": False, "network": False}


def test_entry_write_and_network_capabilities_explicit(tmp_path):
    profile = {"fileSystem": {"entries": [{"access": "write", "path": {"type": "path", "path": str(tmp_path / "output")}}]}, "network": {"enabled": True}}
    assert requested_capabilities(profile) == {"write": True, "network": True}


@pytest.mark.parametrize("profile", [
    {"filesystem": {"read": ["C:/project/tool"]}},
    {"shell": {"allowAll": True}},
    {"fileSystem": {"writeAll": True}},
    {"fileSystem": {"read": "C:/project/tool"}},
    {"fileSystem": {"read": ["../outside"]}},
    {"fileSystem": {"read": ["C:/"]}},
    {"fileSystem": {"read": ["C:/project/../outside"]}},
    {"fileSystem": {"read": ["C:/project/.aws/credentials"]}},
    {"fileSystem": {"globScanMaxDepth": True}},
    {"fileSystem": {"globScanMaxDepth": 100000}},
    {"fileSystem": {"entries": [{"access": "execute", "path": {"type": "path", "path": "C:/tool"}}]}},
    {"fileSystem": {"entries": [{"access": [], "path": {"type": "path", "path": "C:/tool"}}]}},
    {"fileSystem": {"entries": [{"access": "read", "path": {"type": "path", "path": "C:/tool", "future": True}}]}},
    {"fileSystem": {"entries": [{"access": "read", "path": {"type": "special", "value": {"kind": "root"}}}]}},
    {"fileSystem": {"entries": [{"access": "read", "path": {"type": "special", "value": {"kind": []}}}]}},
    {"fileSystem": {"entries": [{"access": "read", "path": {"type": "glob_pattern", "pattern": "**/*"}}]}},
    {"network": {"enabled": True, "all": True}},
    {"network": {"enabled": "true"}},
    {"network": {"enabled": 1}},
    {"network": []},
    [],
    None,
])
def test_unknown_malformed_and_broad_scope_declined(profile):
    with pytest.raises(PermissionProfileError):
        validate_permission_profile(profile)


def test_supported_special_project_subpath_and_readonly_deny_entry():
    profile = {"fileSystem": {"entries": [{"access": "deny", "path": {"type": "special", "value": {"kind": "project_roots", "subpath": "safe/tools"}}}]}}
    assert validate_permission_profile(profile) == profile
    assert requested_capabilities(profile)["write"] is False
