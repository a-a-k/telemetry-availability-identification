"""Assemble source-linked article chapters and optional Pandoc review artifacts.

Only editorial Markdown and previously audited figures are read. No application
observations, model fitting or experimental analysis is performed.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/'docs'
TITLE='Telemetry-Driven Identification of Stochastic Availability Models for Microservice Systems'
SOURCES=[('ARTICLE_INTRODUCTION_V3.md',None),('ARTICLE_METHODS_V3.md','Methods'),
         ('ARTICLE_RESULTS_V3.md','Results'),('ARTICLE_DISCUSSION_V3.md','Discussion'),
         ('ARTICLE_REFERENCES_V3.md',None),('ARTICLE_CLAIMS_V3.md','Appendix: contribution and evidence boundaries')]


def body(path,out,heading):
    text=path.read_text(encoding='utf-8')
    start=re.search(r'^## ',text,re.M)
    if not start:raise ValueError('No chapter body: '+str(path))
    text=text[start.start():]
    if heading:
        text=re.sub(r'^(#{2,}) ',r'\1# ',text,flags=re.M)
        text='## '+heading+'\n\n'+text
    def link(match):
        value=match.group(1)
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',value) or value.startswith('#'):return match.group(0)
        name,sep,fragment=value.partition('#')
        target=(path.parent/name).resolve()
        if not target.exists():raise ValueError('Broken source link: '+value)
        relative=os.path.relpath(target,out).replace('\\','/')
        return ']('+relative+(sep+fragment if sep else '')+')'
    return re.sub(r'\]\(([^)]+)\)',link,text)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,default=DOCS/'manuscript-v3')
    p.add_argument('--pandoc',type=Path)
    p.add_argument('--markdown-only',action='store_true',help='Synchronize only Markdown and its source provenance; leave earlier review exports unchanged')
    args=p.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if args.markdown_only and args.pandoc:p.error('--markdown-only cannot be combined with --pandoc')
    chapters=[];inputs={}
    for name,heading in SOURCES:
        path=DOCS/name;raw=path.read_bytes()
        inputs[path.relative_to(ROOT).as_posix()]=sha256(raw).hexdigest()
        chapters.append(body(path,out,heading))
    # Keep the current draft explicit; main interpretation is never fabricated.
    dispatch=DOCS/'evidence/v3-main-dispatch-v3.json'
    status='Draft for review. The independent main comparison has not yet supplied its audited result section.'
    if dispatch.exists():
        identity=json.loads(dispatch.read_bytes());run=identity['run_id']
        status=f'Draft for review. Independent main run {run} is registered; its audited interpretation must be integrated before submission.'
        result=DOCS/f'tables/v3-main-{run}/README.md'
        if result.exists():
            chapters.append(body(result,out,'Appendix: frozen remote main tables'))
            inputs[result.relative_to(ROOT).as_posix()]=sha256(result.read_bytes()).hexdigest()
    text=(f'---\ntitle: "{TITLE}"\nsubtitle: "Research correction v3 — working manuscript"\nlang: en-GB\n---\n\n'
          +status+'\n\nHistorical audits, technical checks, mechanism evidence and independent comparison have separate scopes. '
          'The original source chapters and complete claim table remain part of this draft.\n\n'+'\n\n'.join(chapters))
    manuscript=out/'manuscript.md';manuscript.write_bytes(text.encode())
    if args.markdown_only:
        provenance=dict(version='v3-markdown-source-sync-v1',title=TITLE,source_sha256=inputs,
            outputs={'manuscript.md':dict(bytes=manuscript.stat().st_size,sha256=sha256(manuscript.read_bytes()).hexdigest())},
            publication_ready=False,model_execution_or_resampling=False,build_status=status,
            historical_review_exports='Earlier assembly-provenance.json describes unchanged historical exports; they are not current source renderings')
        (out/'source-provenance.json').write_bytes((json.dumps(provenance,indent=2)+'\n').encode())
        historical=out/'assembly-provenance.json'
        if historical.exists():
            old=json.loads(historical.read_bytes())
            old['scope']='Historical review-export snapshot; its Markdown was superseded by source-provenance.json'
            old['current_markdown_provenance']='source-provenance.json'
            historical.write_bytes((json.dumps(old,indent=2)+'\n').encode())
        print(json.dumps(dict(markdown_only=True,outputs=provenance['outputs'],publication_ready=False)))
        return
    css=out/'review.css';css.write_bytes(b'body{max-width:72rem;margin:3rem auto;padding:0 2rem;font:17px/1.6 Georgia,serif;color:#18232c}h1,h2,h3,h4{font-family:Arial,sans-serif;line-height:1.3}h2{margin-top:2.8rem}a{color:#146a8a}table{border-collapse:collapse;width:100%;font:13px/1.45 Arial,sans-serif}th,td{border-bottom:1px solid #d0d7de;padding:7px;text-align:left;vertical-align:top}th{background:#eef3f6}img{max-width:100%;height:auto}code{overflow-wrap:anywhere} @page{size:A4;margin:18mm} @media print{body{font-size:11pt;margin:0;max-width:none}table{font-size:8pt}h2{break-after:avoid}tr{break-inside:avoid}}\n')
    version=None
    if args.pandoc:
        executable=str(args.pandoc.resolve())
        version=subprocess.check_output([executable,'--version'],text=True).splitlines()[0]
        review_png=DOCS/'figures/aina-audit-v3-review.png'
        inputs[review_png.relative_to(ROOT).as_posix()]=sha256(review_png.read_bytes()).hexdigest()
        lua=out/'docx-figures.lua'
        lua.write_bytes(b'function Image(image) if image.src:match("aina%-audit%-v3%.svg$") then image.src="../figures/aina-audit-v3-review.png" end return image end\n')
        common=[executable,str(manuscript),'--from=markdown-implicit_figures','--standalone','--toc','--resource-path',str(out)]
        subprocess.run(common+['--embed-resources','--math-method=mathml','--css',str(css),'--output',str(out/'manuscript.html')],check=True,cwd=out)
        subprocess.run(common+['--lua-filter',str(lua),'--output',str(out/'manuscript.docx')],check=True,cwd=out)
    outputs={path.name:dict(bytes=path.stat().st_size,sha256=sha256(path.read_bytes()).hexdigest())
             for path in sorted(out.iterdir()) if path.name in ('manuscript.md','manuscript.html','manuscript.docx','review.css','docx-figures.lua')}
    provenance=dict(version='v3-editorial-assembly-v1',title=TITLE,source_sha256=inputs,outputs=outputs,
        renderer=version,publication_ready=False,model_execution_or_resampling=False,
        excluded_author_fields='No current-manuscript authorship or affiliation is inferred from earlier papers',
        build_status=status)
    (out/'assembly-provenance.json').write_bytes((json.dumps(provenance,indent=2)+'\n').encode())
    (out/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n*.docx binary\n')
    print(json.dumps(dict(renderer=version,outputs=outputs,publication_ready=False)))


if __name__=='__main__':main()
