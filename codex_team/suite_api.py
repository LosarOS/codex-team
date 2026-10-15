"""Local, same-origin API for the five integrated development tools."""
from pathlib import Path
import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from .suite_store import SuiteStore, SuiteConflict
from .intelligence import IntelligenceService
from .task_architect import TaskArchitectService
from .time_machine import TimeMachine
from .budget_guardian import BudgetGuardian
from .qa_arena import QAArena
from .models import RunRequest
from .provider import CodexProvider

class Body(BaseModel):
    model_config=ConfigDict(extra='forbid')
class Analyze(Body):
    refresh: bool=True
class Idea(Body):
    project_id: str
    idea: str=Field(min_length=3,max_length=12000)
class EditSpec(Body):
    sections: dict[str,str]
    expected_version: int=Field(ge=1)
class Version(Body):
    expected_version: int=Field(ge=1)
class AI(Version):
    confirmed: bool=False
class Launch(Version):
    run_options: dict=Field(default_factory=dict)
class Entry(Body):
    category: str
    title: str=Field(min_length=1,max_length=300)
    content: str=Field(max_length=12000)
    sources: list[str]=Field(default_factory=list,max_length=30)
    approved: bool=False
    expected_version: int|None=None
class Budget(Body):
    max_agent_calls: int=Field(default=15,ge=1,le=100)
    max_total_tokens: int|None=Field(default=None,ge=1,le=10**12)
class Checkpoint(Body):
    label: str=Field(default='',max_length=300)
    request_id: str|None=Field(default=None,max_length=100)
class Restore(Body):
    preview_token: str=Field(max_length=128)
    confirmed: bool=False
class RetentionPolicy(Body):
    enabled: bool=Field(default=False,strict=True)
    keep_latest: int|None=Field(default=None,ge=1,le=100000,strict=True)
    max_age_days: int|None=Field(default=None,ge=1,le=100000,strict=True)
class RetentionConfirmation(Body):
    preview_token: str=Field(min_length=1,max_length=128)
    confirmed: bool=Field(default=False,strict=True)
class QAConfig(Body):
    image: str=Field(max_length=300)
    commands: list[dict]=Field(max_length=12)
    required_categories: list[str]=Field(default_factory=lambda:['test'],max_length=5)
    timeout_seconds: int=Field(default=120,ge=1,le=600)
class QASetupVerify(Body):
    image: str=Field(min_length=1,max_length=300)
    confirmed: bool=False
class QAPreview(Body):
    run_id: str|None=None
class QAStart(QAPreview):
    confirmation_token: str=Field(max_length=128)
    confirmed: bool=False
class Confirm(Body):
    confirmed: bool=False

def install_suite(app,root,store,engine,qa_runner=None):
    records=SuiteStore(store)
    intelligence=IntelligenceService(root,store,records)
    architect=TaskArchitectService(root,store,intelligence,records)
    machine=TimeMachine(root,records)
    guardian=BudgetGuardian(store)
    arena=QAArena(root,store,runner=qa_runner)
    app.state.suite={'records':records,'intelligence':intelligence,'architect':architect,'machine':machine,'guardian':guardian,'qa':arena}
    router=APIRouter(prefix='/api/suite')

    @router.get('/projects/{project_id}/intelligence')
    def get_intelligence(project_id:str):
        result=intelligence.get(project_id)
        if result:
            current=intelligence.workspace.snapshot(intelligence.project_root(project_id))['head']
            result['data']['stale']=result['data'].get('head')!=current
        return result
    @router.post('/projects/{project_id}/intelligence')
    def analyze(project_id:str,body:Analyze):
        return intelligence.analyze(project_id,refresh=body.refresh)
    @router.get('/projects/{project_id}/architecture')
    def architecture(project_id:str,limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
        intelligence.project_root(project_id)
        return records.page('architecture',project_id,limit,offset)
    @router.get('/projects/{project_id}/source')
    def source(project_id:str,path:str=Query(max_length=4096)):
        return intelligence.source(project_id,path)
    @router.get('/projects/{project_id}/knowledge')
    def knowledge(project_id:str,q:str=Query('',max_length=1000),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
        return intelligence.search(project_id,q,limit,offset)
    @router.post('/projects/{project_id}/knowledge')
    def add_knowledge(project_id:str,body:Entry):
        return intelligence.save_entry(project_id,**body.model_dump(exclude={'expected_version'}))
    @router.put('/knowledge/{record_id}')
    def update_knowledge(record_id:str,body:Entry):
        row=records.get('knowledge',record_id)
        if body.expected_version is None: raise ValueError('Нужна версия записи')
        return intelligence.save_entry(row['project_id'],**body.model_dump(),record_id=record_id)
    @router.delete('/knowledge/{record_id}')
    def delete_knowledge(record_id:str,body:Version):
        return intelligence.delete_entry(record_id,body.expected_version)
    @router.get('/specifications')
    def specifications(project_id:str,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
        intelligence.project_root(project_id)
        return records.page('specification',project_id,limit,offset)
    @router.post('/specifications')
    def create_spec(body:Idea):
        return architect.create(body.project_id,body.idea)
    @router.get('/specifications/{record_id}')
    def get_spec(record_id:str): return architect.get(record_id)
    @router.put('/specifications/{record_id}')
    def edit_spec(record_id:str,body:EditSpec): return architect.save(record_id,body.sections,body.expected_version)
    @router.post('/specifications/{record_id}/approve')
    def approve_spec(record_id:str,body:Version): return architect.approve(record_id,body.expected_version)
    @router.post('/specifications/{record_id}/ai')
    def ai_spec(record_id:str,body:AI):
        if body.confirmed is not True: raise ValueError('Подтвердите отдельную подготовку через Codex')
        if store.settings().get('execution_backend','codex_chatgpt')!='codex_chatgpt':
            raise ValueError('Для Task Architect выберите официальный Codex / ChatGPT. Платный API не используется.')
        if engine.active: raise ValueError('Дождитесь завершения активной команды перед отдельной AI-подготовкой')
        provider=CodexProvider(root)
        # ai_refine owns its isolated provider and deferred cleanup lifecycle.
        return architect.ai_refine(record_id,provider,True,body.expected_version)
    @router.get('/specifications/{record_id}/ai/status')
    def ai_status(record_id:str):
        return architect.ai_status(record_id)
    @router.post('/specifications/{record_id}/ai/cancel')
    def cancel_ai(record_id:str,body:Body):
        return architect.cancel_ai(record_id)
    @router.post('/specifications/{record_id}/launch')
    def launch_spec(record_id:str,body:Launch):
        with engine.lock:
            if engine.active: raise ValueError('Уже выполняется другой запуск. Дождитесь его завершения.')
            row=architect.get(record_id)
            task=architect.launch_text(record_id,body.expected_version)
            launch_key=f'launch_{record_id}_{body.expected_version}'
            try:
                previous=records.get('specification_launch',launch_key)
                return {**store.run(previous['data']['run_id']),'specification_launch_reused':True}
            except KeyError:
                pass
            options=dict(body.run_options)
            if set(options)&{'workspace','task','project_id','id'}: raise ValueError('Путь и задача определяются утверждённым ТЗ')
            options.setdefault('mode',row['data'].get('recommended_mode','standard'))
            request=RunRequest(workspace=str(intelligence.project_root(row['project_id'])),task=task,**options)
            run=engine.create(request)
            run['task_specification']={'id':record_id,'version':row['version']}
            store.save_run(run)
            records.put('specification_launch',row['project_id'],{'run_id':run['id'],'specification_id':record_id,'version':row['version']},record_id=launch_key)
            return engine.launch(run['id'])
    @router.get('/projects/{project_id}/budget')
    def get_budget(project_id:str):
        store.project(project_id)
        return guardian.project_policy(project_id)
    @router.put('/projects/{project_id}/budget')
    def set_budget(project_id:str,body:Budget): return guardian.set_project_policy(project_id,body.model_dump())
    @router.put('/runs/{run_id}/budget')
    def run_budget(run_id:str,body:Budget): return engine.set_budget_policy(run_id,body.model_dump())
    @router.get('/budget')
    def budget(project_id:str='',date:str='',limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
        return guardian.dashboard(project_id,date,limit,offset)
    @router.get('/projects/{project_id}/checkpoints')
    def checkpoints(project_id:str,q:str=Query('',max_length=1000),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
        return machine.list(project_id,limit,offset,q)
    @router.post('/projects/{project_id}/checkpoints')
    def create_checkpoint(project_id:str,body:Checkpoint):
        with engine.lock:
            if engine.active: raise ValueError('Не создавайте ручную точку во время активного запуска')
            return machine.create(project_id,label=body.label,request_id=body.request_id)
    @router.get('/projects/{project_id}/checkpoints/compare')
    def compare(project_id:str,from_id:str,to_id:str): return machine.compare(project_id,from_id,to_id)
    @router.post('/checkpoints/{checkpoint_id}/preview')
    def restore_preview(checkpoint_id:str):
        row=records.get('git_checkpoint',checkpoint_id)
        return machine.preview(row['project_id'],checkpoint_id)
    @router.post('/checkpoints/{checkpoint_id}/restore')
    def restore_checkpoint(checkpoint_id:str,body:Restore):
        row=records.get('git_checkpoint',checkpoint_id)
        with engine.lock:
            if engine.active: raise ValueError('Дождитесь завершения активного запуска')
            return machine.restore(row['project_id'],checkpoint_id,body.preview_token,body.confirmed)
    @router.get('/projects/{project_id}/retention')
    def checkpoint_retention(project_id:str):
        return machine.retention(project_id)
    @router.put('/projects/{project_id}/retention')
    def checkpoint_retention_policy(project_id:str,body:RetentionPolicy):
        return machine.set_retention_policy(project_id,body.model_dump())
    @router.post('/projects/{project_id}/retention/preview')
    def checkpoint_retention_preview(project_id:str):
        return machine.retention_preview(project_id)
    @router.post('/projects/{project_id}/retention/confirm')
    def checkpoint_retention_confirm(project_id:str,body:RetentionConfirmation):
        with engine.lock:
            if engine.active: raise ValueError('Дождитесь завершения активного запуска перед очисткой точек')
            return machine.retention_confirm(project_id,body.preview_token,body.confirmed)
    @router.get('/projects/{project_id}/qa/config')
    def qa_config(project_id:str): return arena.configuration(project_id)
    @router.put('/projects/{project_id}/qa/config')
    def qa_configure(project_id:str,body:QAConfig): return arena.configure(project_id,body.model_dump())
    @router.get('/projects/{project_id}/qa/discover')
    def discover_qa(project_id:str): return arena.discover(project_id)
    @router.get('/projects/{project_id}/qa/setup')
    def setup_qa(project_id:str): return arena.setup(project_id)
    @router.post('/projects/{project_id}/qa/setup/verify')
    def verify_qa_setup(project_id:str,body:QASetupVerify):
        return arena.verify_setup(project_id,body.image,body.confirmed)
    @router.post('/projects/{project_id}/qa/preview')
    def preview_qa(project_id:str,body:QAPreview): return arena.preview(project_id,body.run_id)
    @router.post('/projects/{project_id}/qa')
    def start_qa(project_id:str,body:QAStart):
        if body.confirmed is not True: raise ValueError('Подтвердите конкретные команды и снимок QA')
        with engine.lock:
            if engine.active: raise ValueError('QA Arena запускается после завершения или паузы команды')
            return arena.start(project_id,body.confirmation_token,body.run_id)
    @router.get('/qa')
    def qa_results(project_id:str,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
        return arena.results(project_id,limit,offset)
    @router.get('/qa/{result_id}')
    def qa_result(result_id:str): return arena.get_result(result_id)
    @router.post('/qa/{result_id}/baseline')
    def qa_baseline(result_id:str,body:Confirm):
        if body.confirmed is not True: raise ValueError('Подтвердите изменение эталона проверок')
        row=arena.get_result(result_id)
        return arena.promote_baseline(row['project_id'],result_id)
    @router.get('/qa/{result_id}/report')
    def qa_report(result_id:str): return {'markdown':arena.report(result_id)}
    app.include_router(router)
    return app.state.suite
