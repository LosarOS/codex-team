/* Pure projections of persisted run data. No provider calls or inferred progress. */
"use strict";
((root) => {
  function attempts(run, events = [], eventsComplete = true) {
    const rows = [], counts = {}, history = run.result_history || [];
    const historyIndex = {};
    // A partial page cannot prove that a started call lacks a completion.
    // Keep the complete persisted results visible until timing history catches up.
    if (!eventsComplete || history.length > events.filter(e=>e.type==="agent_completed").length) events=[];
    for (const event of events) {
      if (event.type === "agent_started" && event.role) {
        const role = event.role, number = counts[role] = (counts[role] || 0) + 1;
        rows.push({key: `event-${event.id}`, role, number, iteration: event.payload?.iteration,
          call: event.payload?.call, started: event.created_at, ended: null, result: null, completed: false, state: "INTERRUPTED"});
      } else if (event.type === "agent_completed") {
        const row = [...rows].reverse().find(r => r.role === event.role && !r.completed);
        if (row) {
          const results = history.filter(r => r.role === row.role);
          const index = historyIndex[row.role] || 0;
          row.result = results[index]?.result || event.payload;
          historyIndex[row.role] = index + 1;
          row.resultNumber = index + 1; row.completed = true; row.ended = event.created_at; row.state = row.result?.verdict || "COMPLETED";
        }
      }
    }
    // Before event history arrives, persisted results remain useful, without invented timing.
    if (!rows.length) {
      for (const [index, entry] of history.entries()) {
        const number = counts[entry.role] = (counts[entry.role] || 0) + 1;
        rows.push({key: `history-${index}`, role: entry.role, number, resultNumber: number, historyOnly: true, iteration: entry.iteration,
          result: entry.result, state: entry.result?.verdict || "COMPLETED"});
      }
      if (!history.length) for (const [role, result] of Object.entries(run.results || {})) {
        counts[role] = 1; rows.push({key: `result-${role}`, role, number: 1, resultNumber: 1, historyOnly: true, result, state: result.verdict || "COMPLETED"});
      }
    }
    const state = String(run.state || "").toUpperCase();
    const last = rows.at(-1);
    if (last && last.completed === false && last.role === run.current_role) {
      last.state = state; last.error = run.error_info?.message || run.error;
    } else if (run.current_role && state !== "DONE" && state !== "COMPLETED" &&
        typeof run.calls === "number" && run.calls > Math.max(history.length, ...rows.map(r=>r.call || 0), 0) &&
        (!last || last.role !== run.current_role || last.result)) {
      // stage points to the unfinished pipeline slot; old results are not current work.
      if ((run.pipeline || [])[run.stage] === run.current_role) {
        const role = run.current_role;
        rows.push({key: `current-${role}-${run.calls}`, role, number: events.length ? (counts[role] || 0) + 1 : null, call: run.calls, state, error: run.error_info?.message || run.error});
      }
    }
    const pipeline = run.pipeline || [];
    if (Number.isInteger(run.stage)) {
      const current = rows.at(-1);
      for (let index = run.stage; index < pipeline.length; index++) {
        const role = pipeline[index];
        if (typeof role !== "string") continue;
        // The current slot is already represented by an actual call. Future slots
        // remain visible even if this role ran earlier (repair/recheck pipelines).
        if (index === run.stage && current?.role === role && run.current_role === role) continue;
        rows.push({key: `planned-${index}`, role, number: 0, state: "WAITING"});
      }
    } else {
      const seen = new Set(rows.map(r => r.role));
      for (const [index, role] of pipeline.entries()) {
        if (typeof role === "string" && !seen.has(role)) {
          rows.push({key: `planned-${index}`, role, number: 0, state: "WAITING"}); seen.add(role);
        }
      }
    }
    return rows;
  }
  function category(event) {
    const type = event.type || "", payload = event.payload || {}, item = payload.item || payload;
    if (/fail|error/i.test(type) || payload.error || item.status === "failed" || (typeof (item.exitCode ?? item.exit_code) === "number" && (item.exitCode ?? item.exit_code) !== 0) || ["FAIL", "CHANGES_REQUIRED"].includes(payload.verdict)) return "errors";
    if (/instruction|steer|approval|action|pause_requested|stop_requested/.test(type)) return "decisions";
    if (/command/.test(type) || /command/i.test(item.type || "") || item.command) return "commands";
    return event.role || /agent|thread|turn|repair/.test(type) ? "agents" : "all";
  }
  const api = {attempts, category};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MissionControl = api;
})(globalThis);
