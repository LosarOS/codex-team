# Providers

Default Codex / ChatGPT использует official SDK и ChatGPT/Device Code login. API account не считается ChatGPT login; AUTH_REQUIRED/USAGE_LIMIT не включает fallback.

Optional OpenAI API выбирается явно после separate billing consent. Ключ хранится в Windows Credential Manager; official custom provider использует fixed https://api.openai.com/v1, responses и env_key. Tool child filters исключают ключ и secret names; CLI arguments/SQLite/prompts его не содержат. Global ChatGPT login в API mode запрещён. [Официальная schema](https://learn.chatgpt.com/docs/config-file/config-reference).

CONFIGURED означает наличие ключа. Explicit Test connection — bounded GET/models без inference; CONNECTED подтверждает только этот запрос, не quota/модель. Rotation сбрасывает verification; active API key нельзя удалить до смены provider. Нет plaintext fallback.

API execution проверен mocks, реальные API paid calls не выполнялись. Native secure-store test использовал unique fake key, удалённый после round-trip.
