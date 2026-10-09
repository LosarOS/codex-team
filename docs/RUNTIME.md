# Runtime

Bundle: Python3.12.14, pywebview6.2.1/pythonnet3.2.1 и official SDK/CLI0.162.1. Separate `_internal/runtime/python/python.exe` содержит standard library/DLLs без project site-packages/auth/caches. Frozen app EXE не используется как Python test runner. CLI binaries — Windows x64; маленькие WebView loader DLL architectures включены для eager imports.

Discovery проверяет project .venv/venv, pyvenv.cfg/base stdlib и bundled/trusted interpreter. Node/.NET SDK/JDK/Rust внешние; detection не устанавливает packages и не запускает project scripts. Read grants точечные, broad home/drive roots запрещены. Наличие runtime не гарантирует dependencies конкретного проекта.

Git и WebView2 нужны отдельно. Windows .NET Framework для GUI не заменяет project .NET SDK. Missing runtime требует установки пользователем/отдельного approval, затем restart PATH и Resume.
