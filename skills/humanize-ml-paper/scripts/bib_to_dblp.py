#!/usr/bin/env python3
"""bib_to_dblp.py IN.bib OUT.bib -- rewrite a verified BibTeX file in the DBLP-condensed style
(the shape of a trimmed DBLP export; `references/latex_source.md` §8 and "Bibliography conversion (tool)"):
short venues ({ICML}, {ICLR}, NeurIPS, {EMNLP} (Findings), Trans. Mach. Learn. Res.), arXiv-only papers as
journal = {CoRR}, volume = {abs/ID}; full author lists (truncated "and others" lists are completed from the
arXiv API, capped at 50); "First Last" names; titles protect only acronyms/camel-case words (the ICML/ICLR
bst lower-cases the rest). Keys are kept. The polish step at the bottom of this file runs automatically.

Input: entries whose metadata you have already verified (title, authors, venue, year; `eprint` for arXiv
papers). An unknown venue stops the run with "unmapped venue: ..." before any network request; add it to
`rules`/`jrules` in venue().
Network: only entries with a truncated author list and an `eprint` trigger arXiv API requests (batches of
20, 3 s apart). DBLP itself blocks scripted access (bot check); the script never contacts it.
Standard library only."""
import re
import sys
import time
import unicodedata
import urllib.request

if len(sys.argv) != 3:
    raise SystemExit(__doc__.split('\n', 1)[0])
SRC, OUT = sys.argv[1], sys.argv[2]
s = open(SRC, encoding='utf-8').read()
def parse(s):
    out=[]; i=0
    while True:
        m=re.compile(r'@(\w+)\s*\{\s*([^,\s]+)\s*,').search(s,i)
        if not m: break
        j=m.end(); d=1; k=j
        while d and k<len(s):
            d += (s[k]=='{') - (s[k]=='}'); k+=1
        body=s[j:k-1]; f={}
        for fm in re.finditer(r'(\w+)\s*=\s*',body):
            p=fm.end()
            if p<len(body) and body[p]=='{':
                dd=1;q=p+1
                while dd and q<len(body):
                    dd += (body[q]=='{') - (body[q]=='}'); q+=1
                val=body[p+1:q-1]
            else:
                q=body.find(',',p); q=len(body) if q<0 else q; val=body[p:q].strip().strip('"')
            f.setdefault(fm.group(1).lower(), re.sub(r'\s+',' ',val).strip())
        out.append((m.group(1).lower(), m.group(2), f)); i=k
    return out
E = parse(s)
for t,k,f in E:
    for x in ('title','year'):
        if x not in f: raise SystemExit(f'entry {k}: missing field {x}')
# combining accents and special letters -> LaTeX escapes (arXiv returns UTF-8 names)
ACC = {'\u0301':"\\'",'\u0300':'\\`','\u0308':'\\"','\u0302':'\\^','\u0303':'\\~','\u0327':'\\c ','\u030c':'\\v ','\u0306':'\\u ','\u030a':'\\r '}
SPECIAL = {'ø':'{\\o}','Ø':'{\\O}','ß':'{\\ss}','ł':'{\\l}','Ł':'{\\L}','æ':'{\\ae}','đ':'{\\dj}','ı':'{\\i}'}
def tex(name):
    out=''
    for ch in name:
        if ch in SPECIAL: out+=SPECIAL[ch]; continue
        dec=unicodedata.normalize('NFD',ch)
        if len(dec)==2 and dec[1] in ACC: out+='{'+ACC[dec[1]]+dec[0]+'}'
        else: out+=ch
    return out
def venue(t, f):
    bt = f.get('booktitle',''); jn = f.get('journal','')
    v = bt or jn
    if not v or v.startswith('arXiv preprint'):
        return ('article', {'journal':'CoRR', 'volume':'abs/'+f['eprint']}) if 'eprint' in f else ('misc', {})
    L = v.lower()
    # conference / workshop full name (substring, lower case) -> DBLP short booktitle; order matters (Findings first)
    rules = [('findings of the association for computational linguistics: emnlp','{EMNLP} (Findings)'),
             ('findings of the association for computational linguistics: naacl','{NAACL} (Findings)'),
             ('findings of the association for computational linguistics: acl','{ACL} (Findings)'),
             ('datasets and benchmarks','NeurIPS'),('neural information processing systems','NeurIPS'),
             ('international conference on machine learning','{ICML}'),('international conference on learning representations','{ICLR}'),
             ('conference on language modeling','{COLM}'),('north american chapter','{NAACL-HLT}'),
             ('annual meeting of the association for computational linguistics','{ACL}'),
             ('empirical methods in natural language processing','{EMNLP}'),('aaai conference','{AAAI}'),
             ('computer vision and pattern recognition','{CVPR}')]
    for key, short in rules:
        if key in L: return ('inproceedings', {'booktitle': short})
    # journal full name -> DBLP short journal; volume/number/pages are kept (TMLR: volume = year when absent)
    jrules = [('transactions on machine learning research','Trans. Mach. Learn. Res.'),('transactions of the association for computational linguistics','Trans. Assoc. Comput. Linguistics'),
              ('ieee transactions on software engineering','{IEEE} Trans. Software Eng.'),('psychological review','Psychological Review'),('annals of statistics','The Annals of Statistics')]
    for key, short in jrules:
        if key in L:
            d={'journal':short}
            for x in ('volume','number','pages'):
                if f.get(x): d[x]=f[x]
            if short.startswith('Trans. Mach.') and 'volume' not in d: d['volume']=f['year']
            return ('article', d)
    # unknown venue: keep the full name (add a short form to the tables above if it recurs)
    return ('inproceedings', {'booktitle': v}) if bt else ('article', {'journal': v})
for t,k,f in E: venue(t, f)  # fail on an unmapped venue before any network request
# full author lists from arXiv for truncated entries
need = [f['eprint'] for t,k,f in E if 'eprint' in f and re.search(r'\band\s+others\b', f.get('author',''))]
full = {}
for b in range(0, len(need), 20):
    ids = ','.join(need[b:b+20])
    url = f'https://export.arxiv.org/api/query?id_list={ids}&max_results=20'
    xml = urllib.request.urlopen(url, timeout=60).read().decode('utf-8')
    for ent in re.findall(r'<entry>(.*?)</entry>', xml, flags=re.S):
        m = re.search(r'<id>https?://arxiv\.org/abs/([^<v]+)(v\d+)?</id>', ent)
        if m: full[m.group(1)] = re.findall(r'<name>([^<]+)</name>', ent)
    time.sleep(3)
PAD = ' ' * 18  # continuation indent of the author field, as DBLP prints it
def fmt_authors(f):
    a = f.get('author','')
    if 'eprint' in f and f['eprint'] in full and re.search(r'\band\s+others\b', a):
        names = [tex(n.strip()) for n in full[f['eprint']]]
        if len(names) > 50: names = names[:50] + ['others']
    else:
        names = [n.strip() for n in re.split(r'\s+and\s+', a) if n.strip()]
    return (' and\n'+PAD).join(names)
out=[]; log=[]
for t,k,f in E:
    typ, fields = venue(t, f)
    lines = [f'  author       = {{{fmt_authors(f)}}}', f'  title        = {{{f["title"]}}}']
    for x in ('booktitle','journal','volume','number','pages'):
        if x in fields: lines.append(f'  {x:<12} = {{{fields[x]}}}')
    if typ=='misc' and f.get('note'): lines.append(f'  note         = {{{f["note"]}}}')
    lines.append(f'  year         = {{{f["year"]}}}')
    out.append(f'@{typ}{{{k},\n' + ',\n'.join(lines) + '\n}\n')
    log.append((k, typ, fields.get('booktitle') or fields.get('journal') or '-', len(re.split(r'\s+and\s+', fmt_authors(f)))))
open(OUT,'w',encoding='utf-8').write('\n'.join(out))
print('entries', len(out), '| full author lists fetched', len(full), 'of', len(need))
for r in log[:12]: print(r)

# ---- polish: titles (brace only acronyms / camel-case / letter+digit words) and "First Last" author order
p=OUT; s=open(p,encoding='utf-8').read()
def needs(w):
    parts=[x for x in re.split(r'[-/]',w) if x]
    return any(re.search(r'[A-Z].*[A-Z]',x) or re.search(r'^.+[A-Z]',x) or (re.search(r'\d',x) and re.search(r'[A-Z]',x)) for x in parts)
def fix_title(m):
    val=m.group(2)
    while val.startswith('{') and val.endswith('}'):
        d=0; ok=True
        for i,ch in enumerate(val):
            d+=(ch=='{')-(ch=='}')
            if d==0 and i<len(val)-1: ok=False; break
        if ok: val=val[1:-1]
        else: break
    res=''; depth=0
    for t in re.split(r'(\s+)',val):
        if t.isspace() or not t: res+=t; continue
        if depth>0 or '{' in t or '}' in t or '\\' in t:
            depth+=t.count('{')-t.count('}'); res+=t; continue
        pre,w,post=re.match(r'^([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9]*)$',t).groups()
        res+=pre+('{'+w+'}' if w and needs(w) else w)+post
    return m.group(1)+'{'+res+'}'
s=re.sub(r'(  title        = )\{(.*)\}(?=,\n)', fix_title, s)
def fix_names(m):
    conv=[]
    for n in re.split(r'\s+and\s*\n\s*', m.group(2)):
        n=n.strip()
        if ',' in n and n!='others':
            last,first=[x.strip() for x in n.split(',',1)]; n=f'{first} {last}'
        conv.append(n)
    return m.group(1)+'{'+(' and\n'+' '*18).join(conv)+'}'
s=re.sub(r'(  author       = )\{(.*?)\}(?=,\n  title)', fix_names, s, flags=re.S)
open(p,'w',encoding='utf-8').write(s)
