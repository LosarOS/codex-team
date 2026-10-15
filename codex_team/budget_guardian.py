"""Observed per-run budgets. Never interprets account quota or estimates cost."""
from collections import defaultdict

THRESHOLDS = (50, 75, 90, 100)


def validate_policy(policy):
    if not isinstance(policy, dict) or set(policy) - {'max_agent_calls', 'max_total_tokens'}:
        raise ValueError('Unsupported budget policy fields')
    result = {}
    for key, value in policy.items():
        if key == 'max_total_tokens' and value is None:
            result[key] = None
            continue
        upper = 100 if key == 'max_agent_calls' else 10**12
        if type(value) is not int or not 1 <= value <= upper:
            raise ValueError(f'Invalid budget value: {key}')
        result[key] = value
    return result


def measured_tokens(entry):
    last = entry.get('last')
    if not isinstance(last, dict):
        return None
    def count(*keys):
        return next((last[k] for k in keys if type(last.get(k)) is int and last[k] >= 0), None)
    total = count('totalTokens', 'total_tokens')
    if total is not None:
        return total
    incoming, outgoing = count('inputTokens', 'input_tokens'), count('outputTokens', 'output_tokens')
    return incoming + outgoing if incoming is not None and outgoing is not None else None


def evaluate(run):
    entries = run.get('usage', [])
    observed = [measured_tokens(e) for e in entries]
    tokens = sum(v for v in observed if v is not None) if any(v is not None for v in observed) else None
    calls, max_calls = run.get('calls', 0), run.get('max_agent_calls', 100)
    max_tokens = run.get('max_total_tokens')
    ratios = {'calls': calls / max_calls if max_calls else 0,
              'tokens': tokens / max_tokens if max_tokens and tokens is not None else None}
    reached = [key for key, value in ratios.items() if value is not None and value >= 1]
    return {'calls': calls, 'measured_tokens': tokens, 'usage_complete': len(entries) == calls and all(v is not None for v in observed),
            'max_agent_calls': max_calls, 'max_total_tokens': max_tokens,
            'percent': {k: round(v * 100, 2) if v is not None else None for k, v in ratios.items()},
            'reached': reached, 'thresholds': {k: [t for t in THRESHOLDS if v is not None and v * 100 >= t] for k, v in ratios.items()},
            'account_quota': None}


class BudgetGuardian:
    def __init__(self, store):
        from codex_team.suite_store import SuiteStore
        self.store, self.records = store, SuiteStore(store)

    def project_policy(self, project_id):
        try:
            return self.records.get('budget_policy', 'budget_' + project_id)['data']
        except KeyError:
            return {}

    def set_project_policy(self, project_id, policy):
        if not any(p['id'] == project_id for p in self.store.projects()):
            raise KeyError(project_id)
        return self.records.put('budget_policy', project_id, validate_policy(policy), record_id="budget_" + project_id)

    def dashboard(self, project_id='', date='', limit=100, offset=0):
        if not 1 <= limit <= 200 or offset < 0:
            raise ValueError('Invalid page')
        project = next((p for p in self.store.projects() if p['id'] == project_id), None) if project_id else None
        if project_id and not project:
            raise KeyError(project_id)
        page = self.store.run_page(limit=limit, offset=offset, project=project['path'] if project else '', date=date)
        items = []
        roles = defaultdict(lambda: {'calls': 0, 'measured_tokens': None})
        for row in page['items']:
            run = self.store.run(row['id'])
            items.append({'id': run['id'], 'task': run.get('task', '')[:400], 'created_at': run.get('created_at'),
                          'state': run['state'], 'usage': [{'agent': e.get('agent'), 'completed_at': e.get('completed_at'), 'measured_tokens': measured_tokens(e)} for e in run.get('usage', [])[-100:]], **evaluate(run)})
            with self.store.lock:
                counts = self.store.db.execute("SELECT role,count(*) FROM events WHERE run_id=? AND type='agent_started' GROUP BY role", (run['id'],)).fetchall()
            for role_name, count in counts:
                roles[role_name or 'unknown']['calls'] += count
            for entry in run.get('usage', []):
                role = roles[entry.get('agent', 'unknown')]
                token = measured_tokens(entry)
                if token is not None:
                    role['measured_tokens'] = (role['measured_tokens'] or 0) + token
        return {'items': items, 'total': page['total'], 'limit': limit, 'offset': offset,
                'roles': dict(roles), 'aggregation_scope': 'current_page', 'account_quota': None,
                'recommendations': ['Для небольших задач рассмотрите Quick.', 'Ограничивайте число повторных проверок бюджетом вызовов.'],
                'policy': self.project_policy(project_id) if project_id else {}}
