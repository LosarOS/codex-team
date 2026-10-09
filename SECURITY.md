# Security

Не помещайте secrets в tasks, prompts, replies или shell commands. Официальные ChatGPT credentials не копируются приложением. Optional API key хранится только в Windows Credential Manager, поступает SDK transport через env_key и исключается из tool child environment. Plaintext fallback отсутствует.

Работа ограничена canonical clean Git root/worktree. Hooks приложения отключены; активные checkout filters отклоняются. Guards проверяют traversal/junction/symlink escapes и sensitive filenames. Только Developer writer; native Codex profile является tool boundary. Action Center grant не отменяет sandbox restrictions.

Filename screening/redaction не является общим secret detector. Native credential deny glob expansion ограничено depth16 до startup; новые/более глубокие sensitive paths и произвольные secret filenames не гарантируются. Diagnostics ZIP ограничен logs/metadata, но его следует просматривать перед передачей.

Backend loopback-only; Host/Origin checks и private shutdown ownership token защищают локальный UI. Native bridge содержит девять fixed methods, project/worktree opening только по ID; remote/file top navigation блокируется. Приложение не защищает пользователя от собственного compromised OS/account.

Для сообщения об уязвимости используйте приватный контакт владельца репозитория; не публикуйте credentials или exploit с пользовательскими данными. Public security contact ещё не настроен. Артефакты приложения unsigned; подписи официальных prerequisite downloads проверяются отдельно.
