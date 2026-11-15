# RC12 master T — настоящие Windows/WebView2 кадры

Source/probe **ccd0500e07c79eca7cbbea1e098f8c05d8e6a0f6**. [Canonical Windows43665690346](https://github.com/LosarOS/codex-team/actions/runs/43665690346), disposable Windows runner, синтетический профиль,1024×768. PNG взяты из исходного GUI archive без изменения байтов; `provenance.json` содержит исходные имена, размеры и SHA256.

1. [Окно, onboarding и готовый backend](native-dashboard-task-form.png): UI-индикатор «Нужен вход» — известная авторизация требует входа, а не отсутствие локального сервера. Ни login, ни mission не запускались.
2. [Предпросмотр бюджета](native-budget-preview.png): реальная пустая синтетическая выборка, null для неизвестных токенов/стоимости/квоты; экран прокручен к JSON и действию сохранения.
3. [Системный Save](native-budget-save-picker.png): настоящий Windows dialog поверх приложения. Английский язык системного диалога соответствует локали runner; приложение показано на русском.

Все три кадра декодированы и просмотрены. На текущем первом кадре нет прежнего ложного offline; исходный C0 startup-frame сохранён отдельно как историческое техническое доказательство и не ретушировался.

[Отдельная проверка GUI evidence](../../../reports/evidence/rc12-main-candidate/independent-gui-evidence-verification.json): все 7 native gates true, exit0, remaining0, no force cleanup, SDK account calls неизвестны (`null`). Физическая Windows/DPI/Narrator/live SDK acceptance этим не подтверждается. Тело записанного JSON не включено в текущий canonical archive. Публикация релиза ещё требует подтверждения владельца.
