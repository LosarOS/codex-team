"""Strict validation of the official 0.162.1 permission-request wire shape.

The generated SDK ignores extra fields in several nested models. A user must
see an exact understood scope before a product can offer a native grant.
This module validates data only; it never grants or executes anything.
"""
import copy
from pathlib import Path, PureWindowsPath


class PermissionProfileError(ValueError):
    pass


def _object(value, fields, label):
    if not isinstance(value, dict) or set(value) - fields:
        raise PermissionProfileError(f"Unsupported {label} fields")


def _path(value):
    if not isinstance(value, str) or not value or len(value) > 4096 or any(c in value for c in "\x00\r\n"):
        raise PermissionProfileError("Permission paths must be bounded absolute paths")
    path = Path(value)
    windows = PureWindowsPath(value)
    if not path.is_absolute() and not windows.is_absolute():
        raise PermissionProfileError("Relative permission paths are ambiguous")
    if ".." in path.parts or ".." in windows.parts:
        raise PermissionProfileError("Permission paths cannot traverse parents")
    if path == Path(path.anchor) or windows == PureWindowsPath(windows.anchor):
        raise PermissionProfileError("Filesystem root grants are unsupported")
    try:
        resolved, home = path.resolve(), Path.home().resolve()
    except (OSError, RuntimeError) as exc:
        raise PermissionProfileError("Permission path cannot be safely resolved") from exc
    if resolved == home or resolved in home.parents:
        raise PermissionProfileError("Whole home-directory or ancestor grants are unsupported")
    parts = [part.lower() for part in windows.parts] + [part.lower() for part in resolved.parts]
    if any(part in {".codex", ".aws", ".ssh", ".azure", ".kube", ".agents"} or part == ".env" or part.startswith(".env.") for part in parts):
        raise PermissionProfileError("Credential permission paths are unsupported")


def _entry_path(value):
    if not isinstance(value, dict):
        raise PermissionProfileError("Permission entry paths must be objects")
    kind = value.get("type")
    if kind == "path":
        _object(value, {"type", "path"}, "path entry")
        _path(value.get("path"))
    elif kind == "special":
        _object(value, {"type", "value"}, "special entry")
        special = value.get("value")
        _object(special, {"kind", "subpath"}, "special path")
        if not isinstance(special.get("kind"), str) or special["kind"] not in {"minimal", "tmpdir", "slash_tmp", "project_roots"}:
            raise PermissionProfileError("Unsupported or broad special permission path")
        subpath = special.get("subpath")
        if subpath is not None:
            if special["kind"] != "project_roots" or not isinstance(subpath, str) or not subpath or len(subpath) > 4096:
                raise PermissionProfileError("Unsupported special subpath")
            relative = PureWindowsPath(subpath)
            if relative.is_absolute() or relative.drive or ".." in relative.parts or any(c in subpath for c in "\x00\r\n"):
                raise PermissionProfileError("Special subpath must stay inside project roots")
            _path(str(Path.cwd() / subpath))
    else:
        # A glob can expand to broad/credential roots that this UI cannot show.
        raise PermissionProfileError("Glob and unknown permission path kinds are unsupported")


def validate_permission_profile(value):
    """Return an exact copy, or fail closed on unknown/malformed/broad scope."""
    _object(value, {"fileSystem", "network"}, "permission profile")
    filesystem = value.get("fileSystem")
    if filesystem is not None:
        _object(filesystem, {"entries", "globScanMaxDepth", "read", "write"}, "fileSystem")
        depth = filesystem.get("globScanMaxDepth")
        if depth is not None and (type(depth) is not int or not 1 <= depth <= 64):
            raise PermissionProfileError("Invalid globScanMaxDepth")
        for mode in ("read", "write"):
            paths = filesystem.get(mode)
            if paths is not None:
                if not isinstance(paths, list) or len(paths) > 256:
                    raise PermissionProfileError("Permission paths must be bounded lists")
                for path in paths:
                    _path(path)
        entries = filesystem.get("entries")
        if entries is not None:
            if not isinstance(entries, list) or len(entries) > 256:
                raise PermissionProfileError("Permission entries must be a bounded list")
            for entry in entries:
                _object(entry, {"access", "path"}, "filesystem entry")
                if not isinstance(entry.get("access"), str) or entry["access"] not in {"read", "write", "deny"}:
                    raise PermissionProfileError("Unsupported filesystem access")
                _entry_path(entry.get("path"))
    network = value.get("network")
    if network is not None:
        _object(network, {"enabled"}, "network")
        if network.get("enabled") is not None and type(network["enabled"]) is not bool:
            raise PermissionProfileError("Network enabled must be a boolean")
    return copy.deepcopy(value)


def requested_capabilities(value):
    """Capabilities for the engine's role gate, after strict scope validation."""
    profile = validate_permission_profile(value)
    filesystem = profile.get("fileSystem") or {}
    return {"write": bool(filesystem.get("write")) or any(entry.get("access") == "write" for entry in filesystem.get("entries") or []),
            "network": (profile.get("network") or {}).get("enabled") is True}
