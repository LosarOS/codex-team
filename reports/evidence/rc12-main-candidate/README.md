# RC12 — финальный кандидат из master T

Версия `1.0.0-rc12`, source/probe **ccd0500e07c79eca7cbbea1e098f8c05d8e6a0f6**.
[Canonical main Windows43665690346](https://github.com/LosarOS/codex-team/actions/runs/43665690346) → [независимый read-only review43667875815](https://github.com/LosarOS/codex-team/actions/runs/43667875815). Обе проверки завершены успешно; публикация Releases не выполнялась.

## Фактически скачанные байты

Скачанные через подключённый GitHub файлы проверены существующим `tools/verify_review_candidate.py`: все три размера и SHA256, CRC/path/duplicate checks внешних и внутренних ZIP, PE, portable marker и named-user-data guards. Installer внутри setup ZIP совпадает с отдельным EXE. Это проверка байтов/сохранённых proofs, не новый Windows runtime run и не универсальный secret scan.

| Файл | Bytes | SHA256 |
| --- | ---: | --- |
| CodexTeam-Portable-x64.zip | 249666849 | ad05e0966417e3173f5dda3847c0d6ddf98b10474459e063d833e3531eb9be65 |
| CodexTeam-Setup-x64.exe | 155694288 | 7d1f9a3d66212037447e2cbf85b0df89deeafc566defac431ab62fb7726e2003 |
| CodexTeam-Setup-x64.zip | 155228614 | 5968713c05b6458f24b88ea8ccd5206bd6480bc2b049a3b407785d9e2be983bd |

[Verifier report](independent-artifact-verification.json), [исходный CLI output](independent-artifact-verification-cli.txt), [исходные sums](SHA256SUMS.txt). Portable ZIP:3219 entries,674620064 uncompressed bytes; приложение PE32+/x64. Installer bootstrap PE32/x86 — нормальный Inno stub для x64-продукта. PE certificate table отсутствует: unsigned. SmartScreen/антивирусы не проверялись.

## Тесты и native acceptance

Windows source suite: **1041 passed / 1 skipped / 1042 total**,0 failures/errors,1043.844s — [оригинал](source-test-results.json). Пропуск — Docker opt-in согласно source run. Последняя полная Linux suite на итоговом коде: [1038 passed / 4 skipped](../rc12-startup-regression/README.md). Платформы, browser checks и повторная байтовая проверка не прибавляются как новые уникальные тесты.

[Отдельный GUI report](independent-gui-evidence-verification.json) проверяет оригинальный canonical proof и GUI ZIP:

- Source и probe точно master T; status OBSERVED_NATIVE_GUI_SCENARIOS_PASSED.
- Все семь обязательных флагов true: window, task form, backend connection, portable marker, picker, saved JSON, graceful quit.
- Фактический UI-индикатор **«Нужен вход»**, после проверки локального backend; ложный offline отсутствует на просмотренном кадре.
- GUI native exit0; fixture exit0; оставшихся owned процессов0; force cleanup=false.
- Login/model execution не запрашивались; **GUI sdk_account_calls=null**, не0. Нулевые counters backend smoke из byte-verifier относятся только к backend-сценариям.
- CRC GUI ZIP прошёл; отдельный proof и proof внутри ZIP совпали побайтово; все три PNG 1024×768 декодированы и просмотрены без редактирования.

Main T archive **не содержит тело сохранённого JSON**. Сохранение/валидация подтверждены исходным runtime proof и кодом smoke; мы не подменяем отсутствующий payload файлом старого эксперимента. Физическая Windows10/11, DPI/Narrator, полный interactive GUI matrix, live SDK mission и длительный soak остаются отдельными gates.

[Три настоящих Windows-снимка и provenance](../../../docs/screenshots/rc12-main-candidate/README.md). Исторические папки 6e/C0/6807 сохранены отдельно. Они не переименованы в T и не заменяют эту проверку.

## Исходные файлы и скачивание

Metadata, release notes, GUI archive и candidate-review скопированы побайтово из review artifact; `original-evidence-manifest.json` фиксирует размеры/SHA256. `.gitattributes` сохраняет исходные BOM/CRLF и явно допускает CR как EOL только внутри этого evidence-каталога. `BUILD-NOTES.txt`/release notes — исходные из сборки, не поздняя редакция документации.

Временные Actions artifacts требуют входа в GitHub. Внешний ZIP Actions содержит исходные дистрибутивы: извлеките installer либо portable ZIP; portable ZIP распакуйте полностью.

- [Portable14143076340](https://github.com/LosarOS/codex-team/actions/runs/43667875815/artifacts/14143076340).
- [Installer EXE/ZIP14142851753](https://github.com/LosarOS/codex-team/actions/runs/43667875815/artifacts/14142851753).
- [Proof/evidence14142457332](https://github.com/LosarOS/codex-team/actions/runs/43667875815/artifacts/14142457332).

Это пригодный для решения владельца кандидат, **не опубликованный GitHub Release**. Старые релизы и tags не изменялись.

Raw `RELEASE-NOTES-RU.md` сохраняет относительные ссылки исходного расположения `docs/releases/`. Для чтения со ссылками используйте [исходный документ exact T](https://github.com/LosarOS/codex-team/blob/ccd0500e07c79eca7cbbea1e098f8c05d8e6a0f6/docs/releases/v1.0.0-rc12.md). Нынешние пользовательские notes подготовлены отдельно; original artifact не редактируется.
