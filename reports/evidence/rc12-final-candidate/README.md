# RC12 — финальный проверенный кандидат C0 (не опубликованный релиз)

Source: `c0e6f8f6c7ffd87d2981b5033e6fd2afa9f80333`, версия `1.0.0-rc12`.
[Canonical Windows build43659810614](https://github.com/LosarOS/codex-team/actions/runs/43659810614) → [независимая read-only сверка43661926960](https://github.com/LosarOS/codex-team/actions/runs/43661926960).

## Реальные байты и исходные доказательства

После успешного canonical workflow файлы повторно скачаны как split review artifacts. Локально `tools/verify_review_candidate.py` проверил все3размера/SHA256, CRC/безопасность путей внешних и внутренних ZIP, PE, portable marker, совпадение installer внутри ZIP с отдельным EXE и отсутствие упакованных данных по именованным path/database guards. Это не универсальный сканер секретов и не новая runtime-проверка. Результат: `independent-artifact-verification.json`, исходный CLI output рядом.

| Бинарник | Bytes | SHA256 |
| --- | ---: | --- |
| CodexTeam-Portable-x64.zip | 249665091 | e0d0d351d3131fa6d37f14f2e245d3b944b9df0a3dc6914fcf62fdfda6a3af40 |
| CodexTeam-Setup-x64.exe | 155696280 | 5e378cd9a21582a5d349d2f3590fb21ec6d30230a91f7b6fc807dd6742deb7dc |
| CodexTeam-Setup-x64.zip | 155231026 | 5177746bb2fa542c42ed84ed93ec217e7a3ff6c34ddf0b3fa065843ff707bea8 |

Приложение: PE32+/x64; Inno installer bootstrap: PE32/x86, содержит тот же установщик x64-продукта. У обоих нет PE certificate table: unsigned. Это не проверка SmartScreen/антивирусов.

Windows source suite: **1025 passed,1 skipped,1026 total**,0failures/errors,984.022s. Пропуск — Docker opt-in согласно исходному запуску. `source-test-results.json` привязан к C0; повторный байтовый verifier не прибавляется к количеству тестов.

Исходные metadata, ZIP evidence и release notes скопированы без редактирования. `original-evidence-manifest.json` фиксирует bytes/SHA256; локальный `.gitattributes` сохраняет исходные переводы строк/BOM. `candidate-review.json` — оригинальный вывод OPS. `BUILD-NOTES.txt` и release notes отражают именно собранный source, а не более поздние изменения документации.

## Отдельная native GUI проверка

`independent-artifact-verification.json` намеренно говорит backend proofs only. Его нулевые model/account counters относятся к backend smoke. **GUI имеет отдельное доказательство** `independent-gui-evidence-verification.json`:

- Source и probe commit точно C0.
- Реальный portable EXE/WebView2, окно/форма/portable marker/native SAVE/сохранённый JSON/graceful quit подтверждены исходным canonical proof.
- GUI native exit code0, owned remaining0, force cleanup false.
- Login/model execution не запрашивались; **GUI sdk_account_calls=null**, не0.
- Оригинальный GUI ZIP прошёл CRC, proof внутри совпал побайтово с отдельным файлом;3PNG декодированы Pillow и просмотрены, без изменения байтов.
- Физическая Windows11, DPI/Narrator и живое выполнение SDK не подтверждены. Локально Windows-приложение не запускалось.

[Снимки и ограничения](../../../docs/screenshots/rc12-final-candidate/README.md). [Технический начальный кадр](native-dashboard-task-form.png) хранится только здесь, вне маркетинговых screenshot-страниц. Он снят во время начального состояния и показывает красный badge «Сервер недоступен»; это наблюдение кадра, а не доказательство постоянной недоступности: последующие budget/API/native Save и quit прошли. Причина не устанавливается по одному изображению. Кадр не ретушировался.

## Скачать кандидаты

Требуется вход в GitHub; Actions artifacts временные, это не публичные GitHub Releases. Архив Actions — внешняя обёртка: извлеките из него исходный portable ZIP либо установщик; portable ZIP затем распакуйте полностью.

- [Portable artifact14140063178](https://github.com/LosarOS/codex-team/actions/runs/43661926960/artifacts/14140063178).
- [Installer artifacts14140411638](https://github.com/LosarOS/codex-team/actions/runs/43661926960/artifacts/14140411638).
- [Proof/evidence artifact14140053435](https://github.com/LosarOS/codex-team/actions/runs/43661926960/artifacts/14140053435).

Публикация не выполнялась. Подготовка финального релиза и пользовательское подтверждение остаются отдельными действиями.
