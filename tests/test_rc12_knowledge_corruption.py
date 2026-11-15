"""Persisted malformed metadata must never become trusted context or mutate on read."""
import copy
import json
import pytest
from test_intelligence import intelligence


@pytest.mark.parametrize('binding',[True,{'head':'0'*40,'files':None}])
def test_truthy_malformed_binding_is_unknown_not_http_failure(intelligence,binding):
    intel,_=intelligence
    row=intel.suite.put('knowledge','p',{'category':'verified_fact','title':'Login','content':'Corrupt metadata','sources':['src/auth.py'],'source_binding':binding})
    found=intel.search('p')['items'][0]
    assert found['freshness']['state']=='unknown'
    assert found['freshness']['captured_head'] is None
    assert json.loads(intel.context('p','Login'))['knowledge']==[]
    assert intel.suite.get('knowledge',row['id'])==row


@pytest.mark.parametrize('patch',[
    {'source_binding':[]},
    {'source_binding':'not-a-binding'},
    {'source_binding':{'head':True,'files':{}}},
    {'source_binding':{'head':None,'files':{}}},
    {'source_binding':{'head':['bad'],'files':{}}},
    {'source_binding':{'head':'not-a-git-hash','files':{}}},
    {'source_binding':{'head':'a'*40,'files':[]}},
    {'source_binding':{'head':'a'*40,'files':{'src/auth.py':True}}},
    {'source_binding':{'head':'a'*40,'files':{'src/auth.py':None}}},
    {'source_binding':{'head':'a'*40,'files':{'src/auth.py':'not-a-digest'}}},
    {'source_binding':{'head':'a'*40,'files':{}}},
    {'sources':None}, {'sources':True}, {'sources':'src/auth.py'},
    {'sources':[{'path':'src/auth.py'}]}, {'sources':[None]},
    {'sources':['']}, {'sources':[]},
])
def test_malformed_persisted_shape_is_unknown_excluded_and_unchanged(intelligence,patch):
    intel,_=intelligence
    valid=intel.save_entry('p','verified_fact','Login','Source-backed knowledge',['src/auth.py'])
    data=copy.deepcopy(valid['data']);data.update(patch)
    stored=intel.suite.put('knowledge','p',data,record_id=valid['id'],expected_version=valid['version'])
    snapshot=copy.deepcopy(stored)
    item=intel.search('p')['items'][0]
    assert item['freshness']['state']=='unknown'
    assert item['freshness']['captured_head'] is None
    assert json.loads(intel.context('p','Login'))['knowledge']==[]
    assert intel.suite.get('knowledge',stored['id'])==snapshot


def test_non_object_persisted_data_is_unknown_without_rewrite(intelligence):
    intel,_=intelligence
    stored=intel.suite.put('knowledge','p',{'title':'Original'})
    # Simulate a damaged persisted value in this disposable database only.
    with intel.store.lock, intel.store.db:
        intel.store.db.execute('UPDATE suite_records SET data=? WHERE id=?',(json.dumps(['malformed','data']),stored['id']))
    stored=intel.suite.get('knowledge',stored['id'])
    assert intel.search('p')['items'][0]['freshness']['state']=='unknown'
    assert json.loads(intel.context('p','Login'))['knowledge']==[]
    assert intel.suite.get('knowledge',stored['id'])==stored
