import json
from pathlib import Path
from .models import AgentSpec, AgentPack

CORE = ("coordinator", "analyst", "developer", "qa", "reviewer", "architect", "final-audit", "security", "performance", "game-logic", "narrative", "business-analyst", "system-analyst", "integration", "frontend", "backend", "documentation")

class Registry:
    def __init__(self, root: Path, store):
        self.root, self.store = root, store
        for name in CORE:
            path = root / "agents" / f"{name}.md"
            if path.exists() and not any(a["name"] == name for a in store.agents()):
                store.save_agent(AgentSpec(name=name, role=name, instructions=path.read_text(encoding="utf-8"),
                                           permission="workspace-write" if name == "developer" else "read-only").model_dump())

    def agents(self):
        agents = self.store.agents()
        # Built-in prompt files are deliberately user-editable; custom instructions live in SQLite.
        for agent in agents:
            agent["builtin"] = agent["name"] in CORE
            path = self.root / "agents" / f"{agent['name']}.md"
            if agent["name"] in CORE and path.exists():
                agent["instructions"] = path.read_text(encoding="utf-8")
        return agents

    def get(self, name):
        agent = next((a for a in self.agents() if a["name"] == name and a["enabled"]), None)
        if not agent:
            raise ValueError(f"Agent is absent or disabled: {name}")
        return agent

    def packs(self):
        builtins = {p.stem: AgentPack.model_validate_json(p.read_text(encoding="utf-8")).model_dump() for p in sorted((self.root / "packs").glob("*.json"))}
        merged = {**builtins, **{p["name"]: p for p in self.store.packs()}}
        return [{**pack, "builtin": name in builtins} for name, pack in sorted(merged.items())]

    def save_pack(self, pack):
        for name in [*pack["agents"], *pack["specialists"]]:
            agent = self.get(name)
            if name in pack["specialists"] and agent["permission"] != "read-only":
                raise ValueError("Specialist reviewers must be read-only")
        if pack["agents"] and any(self.get(name)["permission"] == "workspace-write" and name != "developer" for name in pack["agents"]):
            raise ValueError("Only Developer can write in a pack pipeline")
        self.store.save_pack(pack)

    def pipeline(self, mode, pack_name, specialists):
        pack = next((p for p in self.packs() if p["name"] == pack_name), None)
        if pack is None:
            raise ValueError("Unknown agent pack")
        base = {"quick": ["coordinator", "developer", "qa"],
                "standard": ["coordinator", "analyst", "developer", "qa", "reviewer"],
                "deep": ["coordinator", "analyst", "developer", "qa", "reviewer", "final-audit"],
                "audit": ["coordinator", "analyst", "reviewer", "qa", "final-audit"],
                "plan": ["coordinator", "analyst", "architect"],
                "implement": ["coordinator", "developer", "qa", "reviewer"]}[mode].copy()
        chosen = pack.get("agents", [])
        if chosen:
            mandatory = set(base)
            missing = mandatory - set(chosen)
            if missing:
                raise ValueError("The selected mode requires these core roles in its pack: " + ", ".join(sorted(missing)))
            for role in chosen:
                if role not in base:
                    if self.get(role)["permission"] != "read-only":
                        raise ValueError("Additional pack agents must be read-only")
                    base.insert(base.index("developer") if "developer" in base else 2, role)
        extra = list(dict.fromkeys([*pack.get("specialists", []), *specialists]))
        if mode in {"deep", "audit"}:
            for role in extra:
                if self.get(role)["permission"] != "read-only":
                    raise ValueError("Specialists must be read-only; parallel writer reconciliation is unavailable")
            base[2:2] = extra
        for name in base:
            spec = self.get(name)
            if mode not in spec.get("enabled_modes", ["quick", "standard", "deep", "audit", "plan", "implement"]):
                raise ValueError(f"Agent {name} is disabled for mode {mode}")
        return base
