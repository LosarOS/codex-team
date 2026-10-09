# Permissions

Canonical clean Git root, isolated worktree и baseline guards сохраняют существующую работу. Приложение не выполняет reset/clean/push. Hooks отключены; активные checkout filters отклоняются. Paths проверяются на traversal/symlink/junction и sensitive names.

Developer writer; review agents read-only. Native Codex permission profile ограничивает tools, runtime grants точечные. Local command classifier относится только к application commands и не является перехватчиком native Codex shell.

Action Center требует explicit supported decisions. Unsupported/опасные запросы не разрешаются автоматически; redacted command требует safe rewrite. Grant не отменяет sandbox. Secrets не вставляются в input/prompts/commands; depth16 filename screening и redaction ограничены. [SECURITY](../SECURITY.md).
