"""Render five already-audited AINA aggregate rows; no raw parsing or model fit.

Use an isolated plotting environment with matplotlib==3.10.0. The experimental
requirements and all frozen model/runtime files remain unchanged.
"""
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SOURCE=Path('docs/evidence/original-aina-audit-34231677146/files/summary.json')
OUT=Path('docs/figures')


def main():
    if matplotlib.__version__!='3.10.0':raise ValueError('Use the pinned plotting environment')
    raw=SOURCE.read_bytes()
    if sha256(raw).hexdigest()!='b4abba893f734518bf84fb35efb7899fcb8cb5b138b3ff80580956ff1df79518':
        raise ValueError('Historical compact source bytes changed')
    report=json.loads(raw)
    if report['source_run']!=19590510289 or report['probes']!=2500000 or report['new_independent_campaigns']!=0:
        raise ValueError('Wrong historical compact source')
    rows=[]
    for r in report['aggregate']:
        values=r['recomputed_original_global']
        row=dict(scenario_p=r['p_fail'],original_graph_mc=values['R_model_all_block_mean'],
            observed_probe_frequency=values['R_live_mean'],signed_error_pp=r['signed_model_minus_live_pp'])
        if abs(100*(row['original_graph_mc']-row['observed_probe_frequency'])-row['signed_error_pp'])>1e-10:
            raise ValueError('Compact arithmetic differs')
        rows.append(row)
    if [r['scenario_p'] for r in rows]!=[.1,.3,.5,.7,.9]:raise ValueError('Scenario census differs')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':11,
        'axes.labelsize':10,'axes.spines.top':False,'axes.spines.right':False,
        'pdf.fonttype':42,'ps.fonttype':42,'svg.hashsalt':'aina-audit-v3-figure-v1',
        'axes.axisbelow':True,'savefig.facecolor':'white'})
    fig,axes=plt.subplots(1,2,figsize=(9.0,3.65),layout='constrained',gridspec_kw={'width_ratios':[1.12,1]})
    x=[r['scenario_p'] for r in rows]
    axes[0].plot(x,[100*r['original_graph_mc'] for r in rows],color='#246B8E',marker='o',linewidth=1.7,label='Original graph estimate (MC)')
    axes[0].plot(x,[100*r['observed_probe_frequency'] for r in rows],color='#333333',marker='s',linestyle='--',linewidth=1.5,label='Observed probe frequency')
    axes[0].set(title='(a) Estimate and measurement',xlabel='Declared failure scenario p',ylabel='Aggregate (%)',ylim=(0,100),xticks=x,yticks=range(0,101,20))
    axes[0].legend(loc='upper right',frameon=False,fontsize=8.5)
    axes[0].grid(axis='y',color='#E3E6E8',linewidth=.7)
    errors=[r['signed_error_pp'] for r in rows]
    axes[1].bar(x,errors,width=.12,color=['#246B8E' if y>=0 else '#9C4554' for y in errors],zorder=3)
    axes[1].axhline(0,color='#555555',linewidth=.9)
    axes[1].set(title='(b) Signed difference',xlabel='Declared failure scenario p',ylabel='Graph estimate minus observed (pp)',xticks=x,ylim=(-16,14),yticks=[-15,-10,-5,0,5,10])
    axes[1].grid(axis='y',color='#E3E6E8',linewidth=.7)
    for at,value in zip(x,errors):
        axes[1].text(at,value+(.55 if value>=0 else -.55),f'{value:+.2f}',ha='center',va='bottom' if value>=0 else 'top',fontsize=9)
    OUT.mkdir(parents=True,exist_ok=True);base=OUT/'aina-audit-v3'
    fig.savefig(base.with_suffix('.svg'),metadata={'Date':None,'Title':'Audited original AINA aggregate discrepancy'})
    svg=base.with_suffix('.svg')
    svg.write_bytes(('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n').encode('utf-8'))
    fig.savefig(base.with_suffix('.pdf'),metadata={'CreationDate':None,'ModDate':None,'Title':'Audited original AINA aggregate discrepancy'})
    preview=Path('.smoke/article-figures/aina-audit-v3.png');preview.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(preview,dpi=180);plt.close(fig)
    record=dict(version='aina-compact-figure-v1',source=str(SOURCE.as_posix()),source_sha256=sha256(raw).hexdigest(),
        source_run=report['source_run'],audit_run=report['audit_run'],rows=rows,
        evidence_scope='Historical original endpoint/probe experiment; not the v3 whole-business-operation endpoint',
        interpretation='Descriptive aggregates. No inferential error bars, causal attribution, new MC or independent campaigns. Lines guide the eye across five scenarios.',
        python=platform.python_version(),renderer_packages={name:importlib.metadata.version(name) for name in ('matplotlib','numpy','contourpy','pillow','fonttools','kiwisolver','cycler','pyparsing','python-dateutil')},
        outputs={str(p.as_posix()):dict(bytes=p.stat().st_size,sha256=sha256(p.read_bytes()).hexdigest()) for p in (base.with_suffix('.svg'),base.with_suffix('.pdf'))})
    (OUT/'aina-audit-v3-provenance.json').write_bytes((json.dumps(record,indent=2)+'\n').encode())
    print(json.dumps(dict(outputs=record['outputs'],preview=str(preview))))


if __name__=='__main__':main()
