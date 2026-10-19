"""Prepare a new editor task from saved facts; never resume or execute a run."""
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from .task_drafts import DraftData


def replay_data(run):
    task = run.get('task')
    if not isinstance(task, str) or not task.strip() or len(task) > 30000:
        raise HTTPException(status_code=422, detail='В сохранённом запуске нет корректной постановки до 30 000 символов. Скопируйте нужный текст вручную.')
    warnings = ['security_reset']
    data = DraftData().model_dump()
    data['task'] = task
    original = run.get('original_workspace')
    workspace = original if isinstance(original, str) and original.strip() else run.get('workspace')
    if isinstance(workspace, str) and workspace.strip() and len(workspace) <= 4096:
        data['workspace'] = workspace
    else:
        warnings.append('missing_workspace')
    # Validate one editable field at a time: malformed imported metadata must not
    # erase the task or silently confer security settings. Missing fields keep
    # documented editor defaults; invalid values are explicitly flagged.
    defaults = DraftData().model_dump()
    for field in ('mode', 'pack', 'specialists', 'max_iterations', 'max_agent_calls', 'max_run_duration'):
        if field not in run:
            continue
        try:
            candidate = DraftData.model_validate({**defaults, field: run[field]})
            if field == 'pack' and not candidate.pack.strip():
                raise ValueError('Empty pack')
            data[field] = getattr(candidate, field)
        except (ValidationError, ValueError):
            if 'invalid_settings' not in warnings:
                warnings.append('invalid_settings')
    return data, warnings


def create_run_replay_router(store):
    router = APIRouter(prefix='/api/runs/{run_id}')

    @router.get('/replay')
    def prepare_replay(run_id: str):
        try:
            run = store.run(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail='Запуск не найден. Обновите историю.') from None
        data, warnings = replay_data(run)
        return {'run_id': run_id, 'data': data, 'warnings': warnings}

    return router
