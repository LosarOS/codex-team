# Архитектура

`desktop.py` запускает windowed pywebview/WebView2 и owned backend. `desktop_runtime.py` определяет resources/data paths, SingleInstance, Windows Job, hidden children и bounded startup/shutdown. `desktop_services.py` содержит STA-marshalled NotifyIcon/navigation, recovery marker, notification ledger и diagnostics allowlist. [Desktop details](DESKTOP_ARCHITECTURE.md).

FastAPI/SQLite обеспечивают loopback API, agents/packs/settings/history/events/actions. Engine проходит pipeline; каждую роль обслуживает отдельный официальный Codex thread с snapshot instructions. Provider adapter ограничивает finite RPC и отслеживает owned/inflight clients. API backend — явный custom provider того же SDK, без fallback.

WorkspaceManager создаёт isolated Git worktrees, baseline/diff/checkpoint и project memory. Runtime discovery добавляет точечные interpreter/stdlib grants. Strict structured results плюс current-turn execution ledger задают QA/review completion gates.

Один writer/run владеет data-root lease. Read-only specialists последовательные. Backend/SDK children принадлежат launcher; desktop stop не адресуется чужим процессам. Recovery сохраняет partial changes и повторяет только незавершённый stage. [Permissions](docs/PERMISSIONS.md).

## RC12: план, актуальность контекста и экспорт

Статус раздела: описание реализованных contracts кандидата, не заявление о публикации или полной GUI-приёмке. [Руководство RU](docs/RC12-GUIDE-RU.md) · [English](docs/RC12-GUIDE-EN.md).

### Task Architect и подготовка отдельной задачи

`TaskArchitectService` сохраняет план в отдельной версионированной записи `specification_plan` через существующий SuiteStore. Не более20шагов: стабильный ID, title, acceptance, bounded relative paths и `depends_on`. Проверяются ссылки, дубликаты, циклы, соответствие текущей версии specification и compare-and-swap плана. Вычисленные topological order и file overlaps — подсказки, не исполнительный граф и не доказательство независимости.

Read-only prepare доступен только сохранённому root step без зависимостей. Frontend подтверждает замену текущего черновика, повторно проверяет актуальность плана и неизменность формы. Затем выбирает standard access, isolation и отключённый auto-commit. Ни prepare, ни сохранение плана не создают запуск или запись очереди; обычный explicit start/preflight/permissions остаётся отдельным шагом. Произвольная автоматическая передача результатов между worktrees не добавлена.

### Project Intelligence: источник и freshness

При сохранении записи знаний фиксируются текущий HEAD и ограниченные SHA256 источников. Freshness вычисляется при чтении, не изменяя историю ревизий. Отслеживаются изменения, удаление, untracking и ignore источников, включая незакоммиченные изменения. Состояния: current, stale, review_required, unknown. Совпадающие хеши означают идентичность файлов, а не истинность записанного утверждения.

Legacy/unbound, повреждённые и устаревшие записи остаются доступными для просмотра/редактирования, но не включаются в автоматический контекст до review/save. Контекст ограничен512–12000символами; preview возвращает фактический payload без вызова модели. Репозиторий и знания маркируются как недоверенные данные, не system instructions. Это не гарантия отсутствия секретов в выбранном пользователем тексте.

### Mission Control и Budget Guardian

Timeline — проекция сохранённого ledger: порядок по ID, dedup и фильтрация чужого run. Отсутствующий timestamp не заменяется выдуманным временем/процентом. Подсказки блокировок read-only; existing control/decision endpoints продолжают владеть исполнением.

Budget export формируется backend по разрешённым фильтрам project/UTCday/offset/limit, не более100строк. Scope — current_page; `null`, измеренный0 и partial usage различаются. Экспорт исключает текст задачи, пути и raw provider payload; стоимость и квота аккаунта недоступны. В браузере JSON download использует показанный снимок. В desktop bridge принимаются **только фильтры**, не произвольный клиентский JSON: проверяются trusted origin/readiness и bounded filters, backend refetch делает свежий снимок с теми же фильтрами, затем STA native Save dialog. Browser-preview и native-save могут различаться по свежим данным, что явно объясняется пользователю.

Native writer принимает backend schema1/current_page/no-model report, ограничивает размер, требует JSON-файл без symlink, пишет во временный файл и атомарно заменяет выбранную цель. Cancel/error не вызывает browser fallback. Фактическое завершение WebView2 Save-потока подтверждено отдельным [native GUI proof](reports/evidence/rc12-native-gui/native-gui-proof.json): source `6e00643…`, probe `8c551c0…`, run43659404286 на disposable Windows Server. Записан [JSON пустой выборки](reports/evidence/rc12-native-gui/native-budget-saved.json), затем graceful exit0 без force cleanup и оставшихся owned процессов. Backend/unit checks и открытый picker сами по себе этого не доказывают. Этот ограниченный сценарий не закрывает физические Windows/DPI, все GUI/cancel/error/upgrade варианты, live SDK и новые canonical release gates. SDK account-discovery count в GUI неизвестен (`null`), login/model execution не запрашивались.

### Проверка кандидата

`tools/verify_review_candidate.py` независимо читает скачанные review ZIP, сверяет hashes/sizes/CRC/безопасные пути, AMD64 PE32+ приложения и retained source/native-backend proofs. Это read-only artifact verifier, не Windows runtime rerun, signature trust validation или GUI acceptance. Inno Setup x86 stub допустим для x64 приложения. Публикация и merge остаются отдельными действиями владельца.
