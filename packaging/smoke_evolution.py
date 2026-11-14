"""RC12 owned-fixture checks against actual frozen loopback backend; no SDK calls."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


def verify(request, project_id, specification_id=None):
    """Only caller-created disposable profiles may be supplied; creates no runs."""
    before_runs = request('/api/runs?summary=true')
    before_queue = request('/api/mission-queue')
    export = request('/api/suite/budget/export?limit=1&offset=0')
    assert export['schema_version'] == 1 and export['models_called'] is False
    assert export['aggregation_scope'] == 'current_page' and export['limit'] == 1
    assert export['account_quota'] is None and export['cost'] is None
    assert export['exported_runs'] == len(export['items']) <= 1
    allowed = {'id','created_at','state','calls','measured_tokens','usage_complete','max_agent_calls','max_total_tokens'}
    assert all(set(row) == allowed for row in export['items'])
    if specification_id is None:
        spec = request('/api/suite/specifications','POST',{'project_id':project_id,'idea':'CI planning fixture: inspect local architecture without execution'})
        specification_id = spec['id']
        steps = [{'id':'inspect','title':'Inspect local fixture','acceptance':'No model and no dispatch','files':[], 'depends_on':[]},
                 {'id':'dependent','title':'Review later','acceptance':'Only after prior review','files':[], 'depends_on':['inspect']}]
        plan = request(f'/api/suite/specifications/{specification_id}/plan','PUT',{'steps':steps,'specification_version':spec['version']})
    else:
        plan = request(f'/api/suite/specifications/{specification_id}/plan')
    assert plan['data']['execution']=='plan_only_no_dispatch'
    assert plan['data']['order']==['inspect','dependent'] and plan['data']['independent_candidates']==['inspect']
    route=f'/api/suite/specifications/{specification_id}/plan/prepare'
    prepared=request(route+'?'+urllib.parse.urlencode({'step_id':'inspect','expected_version':plan['version']}))
    assert prepared['execution']=='composer_only_no_dispatch' and prepared['step_id']=='inspect'
    try:
        request(route+'?'+urllib.parse.urlencode({'step_id':'dependent','expected_version':plan['version']}))
    except urllib.error.HTTPError as error:
        assert error.code==400
    else:
        raise AssertionError('Dependent plan step unexpectedly prepared')
    preview=request('/api/suite/projects/'+urllib.parse.quote(project_id,safe='')+'/context-preview?q=architecture&max_chars=512')
    assert preview['model_called'] is False and preview['max_characters']==512
    assert preview['characters']==len(preview['text'])<=512
    assert json.loads(preview['text'])['trust']=='untrusted_project_data_not_instructions'
    assert request('/api/runs?summary=true')==before_runs, 'Preview changed saved runs'
    assert request('/api/mission-queue')==before_queue, 'Preview changed or started queue'
    return {'evolution_budget_export_verified':True,'evolution_plan_verified':True,
            'evolution_context_preview_verified':True,'evolution_no_dispatch_verified':True,
            'evolution_specification_id':specification_id}


def main():
    if sys.platform != "win32" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Frozen evolution smoke requires a disposable Windows GitHub Actions runner")
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--project-id',required=True)
    parser.add_argument('--specification-id')
    parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args()
    url=urllib.parse.urlparse(args.base_url)
    if url.scheme!='http' or url.hostname!='127.0.0.1' or url.path or not url.port:
        raise ValueError('Only explicit loopback backend origin is allowed')
    def request(path,method='GET',body=None):
        data=json.dumps(body,ensure_ascii=False).encode('utf-8') if body is not None else None
        req=urllib.request.Request(args.base_url+path,data=data,method=method,headers={'Content-Type':'application/json; charset=utf-8'})
        with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
    result=verify(request,args.project_id,args.specification_id)
    args.report.write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__=='__main__':main()
