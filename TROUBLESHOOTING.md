# Устранение проблем

**Окно не открывается:** проверьте WebView2, целостность `_internal`, доступ на запись к data root. Startup error предлагает логи в `logs/`. Приложение использует EdgeChromium, fallback на IE нет.

**AUTH_REQUIRED / USAGE_LIMIT:** завершите официальный ChatGPT/Device Code login или дождитесь восстановления usage, затем Resume. API fallback отсутствует. Optional API CONFIGURED означает наличие ключа; явный Test connection проверяет только GET/models, не модель или quota.

**Dirty checkout / worktree mismatch:** сохраните свои изменения перед START; после запуска не меняйте checkpoint вручную. Приложение не выполняет reset/clean и не удаляет вашу работу.

**Missing runtime/dependency:** bundled Python включает stdlib, а не project packages. Node/.NET SDK/JDK/Rust могут требовать отдельной установки; обновите PATH и перезапустите приложение, затем Resume. Discovery не запускает project scripts.

**Окно исчезло, задача работает:** откройте tray. Для полного выхода используйте Quit; active close предлагает tray/stop/cancel. Windows Focus Assist может подавлять balloons.

**Backend crash:** Retry или перезапуск восстанавливают interrupted history. Посмотрите diff перед Resume. Export diagnostics создаёт allowlisted redacted ZIP; просмотрите его перед передачей. Не отправляйте tokens, task database или project secrets.

CLI run/resume и UI не могут одновременно владеть одним data root. Windows MSIX/sandbox host может переопределить LOCALAPPDATA; проверяйте фактический desktop-session.json, используйте явный data root для тестов.
