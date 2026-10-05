import json,re,glob,os,collections
import os as _o
cases={l.split("\t")[0]:l.rstrip("\n").split("\t") for l in open(_o.environ.get("CONN_CASES") or _o.path.join(_o.path.dirname(_o.path.abspath(__file__)),"cases.tsv")) if l.strip() and not l.startswith("#")}
ERR=re.compile(r'"status":\s*404|invalid_auth|not_authed|token_expired|TOOLERR|^ERROR:|"error":\{"code"|AccessDenied|command not found|jq: error|parse error|Please give your|No such file|curl: \(\d+\)|"status":\s*401|"err":"', re.M)
rows=[]; per=collections.defaultdict(list)
import sys
for f in sorted(glob.glob((sys.argv[1] if len(sys.argv)>1 else 'runs')+'/*.jsonl')):
    c,i=os.path.basename(f).rsplit('.',2)[0:2]
    ev=[json.loads(l) for l in open(f) if l.strip().startswith('{')]
    res=[e for e in ev if e.get('type')=='result']
    if not res: rows.append((c,i,'NO RESULT')); per[c].append((False,False,0,0)); continue
    r=res[-1]; text=r.get('result') or ''
    if r.get('is_error') or re.search(r'hit your (weekly|usage) limit|rate limit', text, re.I): rows.append((c,i,'INVALID (account limit / infra)')); continue
    tools=[b for e in ev if e.get('type')=='assistant' for b in e['message']['content'] if b.get('type')=='tool_use']
    results=[b for e in ev if e.get('type')=='user' and isinstance(e['message'].get('content'),list) for b in e['message']['content'] if b.get('type')=='tool_result']
    def txt(b):
        x=b.get('content'); return x if isinstance(x,str) else ' '.join(y.get('text','') for y in (x or []) if isinstance(y,dict))
    fails=[txt(b)[:160] for b in results if b.get('is_error') or ERR.search(txt(b))]
    skill=any(t['name']=='Skill' and re.search('connector|google',json.dumps(t['input'])) for t in tools)
    mcp=any(t['name'].startswith('mcp__') for t in tools)
    ok=bool(re.search(cases[c][2], text, re.I))
    first=ok and not fails
    per[c].append((ok,first,r.get('total_cost_usd',0),r.get('num_turns',0)))
    rows.append((c,i,f"task={'✅' if ok else '❌'} first-try={'✅' if first else '❌'} skill={skill} mcp={mcp} fails={len(fails)} turns={r.get('num_turns')} ${r.get('total_cost_usd',0):.2f}", fails))
for row in rows:
    print(row[0].ljust(18),row[1],row[2])
    for fl in (row[3] if len(row)>3 else [])[:2]: print('      fail:',fl.replace('\n',' ')[:150])
by=collections.defaultdict(list)
for c,v in per.items(): by[c.split('-')[0]].extend(v)
print('\nCONNECTOR   runs  task-success  first-try')
T=F=N=0
for k,v in sorted(by.items()):
    n=len(v); t=sum(x[0] for x in v); f=sum(x[1] for x in v); T+=t;F+=f;N+=n
    print(f"{k:10}  {n:4}  {100*t/n:5.0f}%        {100*f/n:5.0f}%")
inv=sum(1 for r in rows if 'INVALID' in str(r[2]))
if N: print(f"{'TOTAL':10}  {N:4}  {100*T/N:5.0f}%        {100*F/N:5.0f}%   cost ${sum(x[2] for v in per.values() for x in v):.2f}")
else: print("No valid runs to score.")
if inv: print(f"{inv} run(s) skipped as invalid (account limit or infra), not counted above")
