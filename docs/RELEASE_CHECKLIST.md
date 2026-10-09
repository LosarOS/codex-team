# RC release checklist

Source evidence: baseline321pass3skip, desktop71pass1skip и native source smoke PASS. Actual runtime checkpoint installedDONE/Resume/reinstall отражён в reports/runtime-baseline-acceptance.json. Это не заменяет финальный polished build acceptance.

Перед выпуском подтвердите:

- reports/rc-final-build.log завершён exit0.
- packaging/build-verification.json проверяет version/resources/CLI и executable Python stdlib imports.
- installer/CodexTeam-Setup-x64.exe и dist/CodexTeam-Portable-x64.zip соответствуют текущей source.
- packaging/release-checksums.json содержит actual final SHA-256/bytes; ZIP CRC pass.
- portable.json только в ZIP, installer/data payload без auth/state; portable root writable и отдельный.
- Final frozen/installed UI ready, tray/recovery/diagnostics и owned-process cleanup проверены; baseline history/settings/auth сохранены.
- Итоговый release report различает actual baseline/source/final и mock-only API checks.

Версии: Python1.0.0rc1, UI/installer1.0.0-rc1, PE1.0.0.0. Application unsigned; general clean-machine matrix/API inference не заявляются. Старые артефакты с тем же filename не подтверждают новый release.
