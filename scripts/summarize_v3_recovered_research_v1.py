"""Descriptive arithmetic on retained main metrics, bounds and recorded costs.

Run after the main recovery/archive retainers and both original table exporters.
No native telemetry, model execution, solver, bootstrap or new inference family.
"""
from pathlib import Path
import csv,io,json,statistics
from collections import defaultdict,Counter
from hashlib import sha256
from datetime import datetime
root=Path('docs/evidence/v3-main-transport-recovery-34517752889')
source=root/'analysis/files/comparison.json'
source_bytes=source.read_bytes()
if sha256(source_bytes).hexdigest() != '10144b774f57623070cd5057e783be1aade32cd7e8b946e1830f9a7c8eff2ccf':
 raise ValueError('The verified recovery comparison has changed')
d=json.loads(source_bytes);a=d['analysis']
out=Path('docs/tables/v3-main-recovered-34517752889/research-interpretation');out.mkdir(parents=True,exist_ok=True)
def csvwrite(name,rows):
 s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
 (out/name).write_bytes(s.getvalue().encode())
bounds=[];coverage=Counter();pairs=Counter();cells=defaultdict(dict)
for row in a['attempted_census']:
 cells[row['application'],row['campaign_id'],row['operation']][row['method']]=row
 if row['method']=='Gstar':
  f=row['forecast'];coverage[row['application'],f['status'],f.get('reason')]+=1
  if 'identified_lower' in f:
   bounds.append(dict(application=row['application'],campaign_id=row['campaign_id'],operation=row['operation'],
       lower=f['identified_lower'],upper=f['identified_upper'],lower_exact=f['lower_exact'],upper_exact=f['upper_exact'],
       width_pp=100*(f['identified_upper']-f['identified_lower']),
       scope='identified calibration-event interval under empirical Q; not a population or future-business confidence interval'))
for rs in cells.values():
 for method in ('Gselected','G_without_deadline','G_without_selection','G_without_completion'):
  pairs[method,rs['Gstar']['forecast']['status']=='ok',rs[method]['forecast']['status']=='ok']+=1
descriptive=[]
for app in a['applications']:
 for method in ('GID','Gselected','G_without_deadline','G_without_selection','G_without_completion','B0'):
  differences=[];same=0
  for (application,campaign,operation),rows in cells.items():
   if application!=app:continue
   left,right=rows['Gstar'],rows[method]
   if left['metrics'] is None or right['metrics'] is None:continue
   differences.append(left['metrics']['absolute_error_pp']-right['metrics']['absolute_error_pp'])
   same+=abs(left['forecast']['probability']-right['forecast']['probability'])<1e-12
  descriptive.append(dict(application=app,right=method,common_cells=len(differences),
   pooled_cell_mean_ae_difference_pp=sum(differences)/len(differences) if differences else None,
   smaller_ae=sum(x < -1e-10 for x in differences),equal_ae=sum(abs(x)<=1e-10 for x in differences),
   larger_ae=sum(x>1e-10 for x in differences),same_forecast=same,
   scope='descriptive equal-cell comparison on paired point support; not primary campaign estimand; no new inference'))
csvwrite('descriptive-paired-ablation-errors.csv',descriptive)
csvwrite('identified-intervals.csv',bounds)
csvwrite('gstar-identification-coverage.csv',[dict(application=k[0],status=k[1],reason=k[2],cells=v) for k,v in sorted(coverage.items())])
csvwrite('point-identification-pairs.csv',[dict(comparator=k[0],Gstar_point=k[1],comparator_point=k[2],cells=v) for k,v in sorted(pairs.items())])
timers=list(csv.DictReader(Path('docs/tables/v3-main-recovered-34517752889/cost-scopes/pmx-model-timings.csv').open(encoding='utf-8',newline='')))
groups=defaultdict(list)
for row in timers:
 if row['load_solve_elapsed_nanoseconds']:groups[row['campaign_id'].split('/')[1],row['variant']].append(int(row['load_solve_elapsed_nanoseconds'])/1e9)
timing=[dict(application=k[0],variant=k[1],records=len(v),median_seconds=statistics.median(v),min_seconds=min(v),max_seconds=max(v),
 scope='load plus solve of one model; two verification passes; not end-to-end campaign cost') for k,v in groups.items()]
csvwrite('pmx-model-timing-summary.csv',timing)
resources=list(csv.DictReader(Path('docs/evidence/v3-main-durable-archive-34516536673/pmx-process-resources.csv').open(encoding='utf-8',newline='')))
graph=list(csv.DictReader(Path('docs/tables/v3-main-recovered-34517752889/cost-scopes/process-resources.csv').open(encoding='utf-8',newline='')))
groups=defaultdict(list)
for row in resources:
 if row['measurement_present']=='True':
  app=row['artifact_name'].removeprefix('v3-comparison-pmx-extraction-').split('--')[0]
  groups[app,'PMX complete extraction command'].append(row)
for row in graph:
 if row['job_role']=='graph' and row['path']=='build-resource-usage.txt':
  groups[row['campaign_id'].split('/')[1],'Graph complete build command'].append(row)
process_summary=[]
for (app,label),rows in groups.items():
 process_summary.append(dict(application=app,scope=label,records=len(rows),
   median_wall_seconds=statistics.median(float(x['wall_seconds']) for x in rows),
   median_cpu_seconds=statistics.median(float(x['user_seconds'])+float(x['system_seconds']) for x in rows),
   median_maximum_rss_mib=statistics.median(float(x['maximum_rss_bytes'])/2**20 for x in rows)))
csvwrite('campaign-process-cost-summary.csv',process_summary)
original=Path('docs/evidence/v3-comparison-main-34465226083')
artifacts=json.loads((original/'all-artifact-metadata.json').read_bytes());jobs=json.loads((original/'jobs-api.json').read_bytes())
extractions=[x for x in artifacts if x['name'].startswith('v3-comparison-pmx-extraction-')]
first=min(datetime.fromisoformat(j['started_at']) for j in jobs if j['name'].startswith('evaluate ('))
assert len(extractions)==241 and all(datetime.fromisoformat(x['updated_at'])<first for x in extractions)
proof=dict(version='v3-main-saved-model-preopening-commitment-v1',source_run=34465226083,
 source_head='d857ea65ca9da7fa9ae4ee1198317487475246a7',recovery_run=34517752889,
 original_artifact_metadata_sha256=sha256((original/'all-artifact-metadata.json').read_bytes()).hexdigest(),
 original_jobs_metadata_sha256=sha256((original/'jobs-api.json').read_bytes()).hexdigest(),
 source_extraction_artifacts=241,latest_source_artifact_update=max(x['updated_at'] for x in extractions),
 first_original_evaluator_job_started_at=first.isoformat(),all_pmx_model_artifacts_precede_original_evaluation=True,
 literal_numerical_pmx_forecast_before_original_opening=False,
 inference='The calibration-derived PCM bytes and scientific solver specification were committed before first evaluation; later unchanged-source solving materializes their predictions. This does not restore the original literal numeric-freeze gate.',
 original_artifacts=[{k:x[k] for k in ('id','name','digest','created_at','updated_at')} for x in sorted(extractions,key=lambda x:x['name'])])
(root/'model-precommitment.json').write_bytes((json.dumps(proof,indent=2)+'\n').encode())
readme='''# Descriptive research interpretation tables

Source comparison SHA256: `10144b774f57623070cd5057e783be1aade32cd7e8b946e1830f9a7c8eff2ccf`, recovery34517752889 on the original240campaigns. These tables use only already computed compact forecasts, count summaries, errors and timings. They add no model fit, solver, bootstrap, confidence interval, test outcome or inference family.

Paired ablation differences weight each available common operation cell equally. They are descriptive and are not the primary equal-condition/equal-operation complete-campaign contrasts. Positive differences mean higher Gstar absolute error. Ties use1e-10pp; identical forecasts use1e-12probability tolerance. Identified intervals concern the calibration model event under empirical Q; they are not population confidence intervals or guaranteed bounds for future business success.

The PMX model timers include load and solve of one model/verification pass. The campaign process table distinguishes complete graph construction from complete PMX extraction; PMX additionally requires the separately recorded Palladio solving/build batches. GNU-time CPU/RSS are process-and-accounted-child measurements, not total container/runner resources. No end-to-end speed ratio is derived.
'''
(out/'README.md').write_bytes(readme.encode())
(out/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
(out/'provenance.json').write_bytes((json.dumps(dict(source=source.as_posix(),source_sha256=sha256(source_bytes).hexdigest(),
 local_model_or_solver_or_bootstrap_execution=False,descriptive_arithmetic_on_existing_compact_values=True,
 outputs={p.name:dict(bytes=p.stat().st_size,sha256=sha256(p.read_bytes()).hexdigest()) for p in sorted(out.iterdir()) if p.is_file() and p.name!='provenance.json'}),indent=2)+'\n').encode())
print(json.dumps({'identified_intervals':len(bounds),'process_cost_summary':process_summary,'preopening_model_commitment':{k:v for k,v in proof.items() if k!='original_artifacts'}},indent=2))
