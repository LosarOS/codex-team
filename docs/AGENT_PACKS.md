# Agent packs

Agent identifier начинается lowercase letter и допускает digits/hyphens/underscores. Задайте role/instructions/model/effort/enabled modes/can_execute и permission без secrets. Core review roles read-only; только Developer writer.

Pack задаёт name/title/description/default_mode/agents/specialists. Core roles режима обязательны; дополнительные agents/specialists должны быть read-only и существуют в registry. Specialists Deep/Audit выполняются последовательно.

Пример: `{"name":"my-pack","title":"Extra review","description":"","default_mode":"deep","agents":[],"specialists":["my-reviewer"]}`.

Editable prompts — user-root agents/, bundled packs — packs/, custom UI definitions — storage. Existing prompt edits сохраняются при обновлении. Каждый run сохраняет snapshot roles; changes применяются к будущим runs. Не редактируйте `_internal`.
