"""Small independent probability/identity oracles for newly represented DB calls."""
from dataclasses import replace
from .pmx_request_controls import fixture
from .pmx_database_client_adapter import project_campaign
from .pmx_request_context import contextualize

SUCCESS={'database_propagated':dict(inclusive=.576,conditional_local=.8),
         'shared_database_two_callers':dict(inclusive=.59049,conditional_local=.81)}
ATTRS={'db.system':'mysql','server.address':'database','server.port':3306,'db.name':'fixture',
       'db.operation':'SELECT','db.statement':'SELECT value FROM fixture WHERE id=?'}


def control(case):
    if case not in SUCCESS:
        raise ValueError('unknown database construct control')
    _,_,grouped,requests=fixture('nested_propagated')
    for row in requests:
        row['operation']=case
    for index,(trace,spans) in enumerate(grouped.items()):
        if case=='database_propagated':
            spans[1]=replace(spans[1],service='front',server=False,native_kind='3',attributes=dict(ATTRS),operation='SELECT fixture')
        else:
            root,child,sibling=spans
            failed=index==0
            caller_a=replace(root,service='caller-a',operation='handle',error_tag=failed,duration_us=10000)
            db_a=replace(child,service='caller-a',operation='SELECT fixture',server=False,native_kind='3',attributes=dict(ATTRS),error_tag=failed)
            caller_b=replace(sibling,service='caller-b',operation='handle',parent_id='',error_tag=failed,
                             start_us=root.start_us+15000,duration_us=10000)
            db_b=replace(db_a,span_id=f'{4:016x}',parent_id=caller_b.span_id,service='caller-b',start_us=caller_b.start_us+1000)
            grouped[trace]=[caller_a,db_a,caller_b,db_b]
            requests[index]['semantic_success']=not failed
    result=contextualize(project_campaign(grouped,requests,declared_host='fixture-worker'))
    return result,SUCCESS[case],grouped,requests
