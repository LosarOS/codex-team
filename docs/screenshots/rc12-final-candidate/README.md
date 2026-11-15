# RC12 C0 — оригинальные снимки Windows/WebView2

Source/probe: `c0e6f8f6c7ffd87d2981b5033e6fd2afa9f80333`.
[Canonical workflow43659810614](https://github.com/LosarOS/codex-team/actions/runs/43659810614), disposable Windows runner,1024×768, синтетический профиль. Файлы перенесены из canonical GUI archive без изменений; происхождение, размеры и SHA256 — `provenance.json`.

- [Реальный budget preview](native-budget-preview.png). Экран прокручен к JSON и кнопке сохранения; пустая выборка и null — реальные синтетические данные сценария.
- [Настоящий системный Save dialog](native-budget-save-picker.png). Русский интерфейс приложения и английский системный диалог на английском runner; picker не нарисован и не внедрён через browser fixture.

Технический начальный кадр сохранён [только в исходных доказательствах](../../../reports/evidence/rc12-final-candidate/native-dashboard-task-form.png): он показывает ранний badge «Сервер недоступен», до последующего успешного budget/API/Save. Это не доказательство постоянного дефекта; кадр не используется как маркетинговый пример.

Последующие сохранение JSON и graceful exit подтверждены `native-gui-proof.json`. [Независимая проверка исходных proofs и PNG](../../../reports/evidence/rc12-final-candidate/independent-gui-evidence-verification.json). Заявленные native-сценарии ограничены этим smoke; physical Win11/DPI/Narrator/live SDK не проверены. Публикации релиза нет.
