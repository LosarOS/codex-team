# RC12 — настоящая Windows WebView2 GUI-проверка

[Успешный эксперимент43659404286](https://github.com/LosarOS/codex-team/actions/runs/43659404286). Реальный portable EXE source `6e00643676dd9b2e701fdccf50fa8b75ff59fd00`; отдельный probe `8c551c08fd8369ba47442a2627cbb0bb8b63b3cb`. Disposable Windows Server runner, один экран1024×768. Это не browser mock и не физическая приёмка Windows11/DPI.

Все четыре PNG просмотрены и перенесены **без изменения байтов**. Видимый временный путь принадлежит исключительно disposable CI fixture; это не личный путь пользователя. [Исходные имена и SHA256](../../../reports/evidence/rc12-native-gui/provenance.json).

| Кадр | Что действительно видно |
| --- | --- |
| [Начальный Dashboard](native-dashboard-task-form.png) | Первое настоящее окно, пустые состояния. Account discovery ещё показывает «Подключение…». Task form обнаружена UIA ниже fold; в этом кадре сама форма не видна. |
| [Budget preview](native-budget-preview.png) | Реальный серверный снимок пустой выборки, null для неизвестных токенов/стоимости/квоты, действие «Скачать JSON». Верх preview за пределами текущего scroll. |
| [Native Save picker](native-budget-save-picker.png) | Настоящий Windows Save As, JSON filter и исходное предлагаемое имя. |
| [Выбранный путь](native-budget-selected-path.png) | Точно выбранный путь внутри owned test directory перед настоящим Save. |

Проверены: окно, доступная форма, portable marker/profile, native JSON export и настоящий graceful quit с exit0 и отсутствием owned GUI/backend-процессов. Принудительная очистка **не использовалась**. Сохранённый файл и [proof](../../../reports/evidence/rc12-native-gui/native-gui-proof.json) приложены.

Аккаунт не подключался, задача/модель не запускались. Startup account discovery происходит штатно; число SDK account calls неизвестно (`null`), а не0. Отдельно остаются NOT VERIFIED: физические Windows10/11, DPI/Narrator/multi-monitor, live SDK development, полный GUI/install/upgrade/soak matrix.
