# Read existing shortcuts through the Unicode Shell Link API. Never resolves,
# saves or launches a shortcut, and never invokes its target.
if (-not ('CodexTeamShortcutReader' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;

[ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ICodexTeamShellLinkW {
    void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int size, IntPtr findData, uint flags);
    void GetIDList(out IntPtr list);
    void SetIDList(IntPtr list);
    void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder text, int size);
    void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string text);
    void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int size);
    void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string path);
    void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder arguments, int size);
    void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string arguments);
    void GetHotkey(out short hotkey);
    void SetHotkey(short hotkey);
    void GetShowCmd(out int command);
    void SetShowCmd(int command);
    void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int size, out int index);
    void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string path, int index);
    void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, uint reserved);
    void Resolve(IntPtr window, uint flags);
    void SetPath([MarshalAs(UnmanagedType.LPWStr)] string path);
}
public static class CodexTeamShortcutReader {
    public static string[] Read(string path) {
        path = Path.GetFullPath(path);
        if (!File.Exists(path)) throw new FileNotFoundException("Shortcut is missing", path);
        object instance = Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("00021401-0000-0000-C000-000000000046")));
        try {
            ((IPersistFile)instance).Load(path, 0);
            var link = (ICodexTeamShellLinkW)instance;
            var target = new StringBuilder(32768);
            var directory = new StringBuilder(32768);
            link.GetPath(target, target.Capacity, IntPtr.Zero, 4);
            link.GetWorkingDirectory(directory, directory.Capacity);
            return new[] { target.ToString(), directory.ToString() };
        } finally { Marshal.FinalReleaseComObject(instance); }
    }
}
'@
}
function Read-ShortcutDetails([string]$Path) {
    $details = [CodexTeamShortcutReader]::Read($Path)
    [PSCustomObject]@{ TargetPath = $details[0]; WorkingDirectory = $details[1] }
}
