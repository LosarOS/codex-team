"""Per-user Windows Credential Manager. No plaintext production fallback."""
import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path


class SecretStoreError(ValueError):
    pass


class WindowsSecretStore:
    def __init__(self, app_root):
        identity = str(Path(app_root).resolve()).casefold().encode('utf-8')
        self.target = 'CodexTeam/OpenAIAPI/' + hashlib.sha256(identity).hexdigest()[:24]

    @staticmethod
    def _api():
        if os.name != 'nt':
            raise SecretStoreError('Secure API key storage requires Windows Credential Manager on this platform')
        class Credential(ctypes.Structure):
            _fields_ = [('Flags',wintypes.DWORD),('Type',wintypes.DWORD),('TargetName',wintypes.LPWSTR),
                        ('Comment',wintypes.LPWSTR),('LastWritten',wintypes.FILETIME),('CredentialBlobSize',wintypes.DWORD),
                        ('CredentialBlob',ctypes.POINTER(ctypes.c_ubyte)),('Persist',wintypes.DWORD),('AttributeCount',wintypes.DWORD),
                        ('Attributes',ctypes.c_void_p),('TargetAlias',wintypes.LPWSTR),('UserName',wintypes.LPWSTR)]
        api = ctypes.WinDLL('advapi32',use_last_error=True)
        api.CredWriteW.argtypes = [ctypes.POINTER(Credential),wintypes.DWORD]
        api.CredWriteW.restype = wintypes.BOOL
        api.CredReadW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(ctypes.POINTER(Credential))]
        api.CredReadW.restype = wintypes.BOOL
        api.CredDeleteW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD]
        api.CredDeleteW.restype = wintypes.BOOL
        api.CredFree.argtypes = [ctypes.c_void_p]
        return api, Credential

    def save(self, key):
        if not isinstance(key,str) or not key.strip() or any(c.isspace() for c in key) or len(key.encode('utf-8')) > 2400:
            raise SecretStoreError('Enter a valid API key without spaces')
        api, Credential = self._api()
        payload = key.encode('utf-8')
        blob = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
        credential = Credential(Type=1,TargetName=self.target,Comment='Codex Team optional OpenAI API provider',
                                CredentialBlobSize=len(payload),CredentialBlob=blob,Persist=2,UserName='OpenAI API')
        if not api.CredWriteW(ctypes.byref(credential),0):
            raise SecretStoreError(f'Windows Credential Manager could not save the key (error {ctypes.get_last_error()})')

    def read(self):
        api, Credential = self._api()
        pointer = ctypes.POINTER(Credential)()
        if not api.CredReadW(self.target,1,0,ctypes.byref(pointer)):
            error = ctypes.get_last_error()
            if error == 1168:
                return None
            raise SecretStoreError(f'Windows Credential Manager could not read the key (error {error})')
        try:
            return ctypes.string_at(pointer.contents.CredentialBlob,pointer.contents.CredentialBlobSize).decode('utf-8')
        finally:
            api.CredFree(pointer)

    def remove(self):
        api, _ = self._api()
        if not api.CredDeleteW(self.target,1,0) and ctypes.get_last_error() != 1168:
            raise SecretStoreError(f'Windows Credential Manager could not remove the key (error {ctypes.get_last_error()})')

    def status(self):
        key = self.read()
        return {'configured': bool(key), 'key_hint': '••••' + key[-4:] if key else None}


class MemorySecretStore:
    """Explicitly injected test double; never selected by production code."""
    def __init__(self):
        self._key = None
    def save(self,key):
        if not isinstance(key,str) or not key.strip():
            raise SecretStoreError('Key required')
        self._key = key
    def read(self):
        return self._key
    def remove(self):
        self._key = None
    def status(self):
        return {'configured': bool(self._key), 'key_hint': '••••' + self._key[-4:] if self._key else None}
