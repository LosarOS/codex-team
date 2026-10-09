# Contributing

Работайте в отдельной Git branch, сохраняйте clean baseline и не коммитьте auth, API keys, logs/task database или build outputs. Python stdlib предпочитается для runtime logic; dependencies закреплены в project requirements.

Из исходников: setup.ps1, затем `.venv/Scripts/python.exe -m pytest -q`. SDK/HTTP tests используют mocks; реальные provider/demo scripts — только explicit opt-in пользователя, с его usage/billing. Изменения lifecycle проверяйте owned child cleanup; Windows native smoke использует отдельный data root и mock endpoints.

PR должен объяснить trigger, поведение и relevant tests. Не объявляйте DONE по model summary без execution evidence. При security concern используйте приватный контакт владельца; secret data не публикуйте. New provider не может добавлять silent fallback или менять global login.
