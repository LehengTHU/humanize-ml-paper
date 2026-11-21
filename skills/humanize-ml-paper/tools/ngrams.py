#!/usr/bin/env python3
"""Top n-grams / sentence openers by group.
usage: ngrams.py --corpus DIR/corpus.jsonl [-g mine] [-n 2,3,4] [--min-papers 3] [--top 200] [--openers] [--region main] [--contains WORD]
                 (default corpus: $STYLE_CORPUS, else ./style_corpus/corpus.jsonl)"""
import json, os, re, argparse, collections
here=os.path.dirname(os.path.abspath(__file__))
ap=argparse.ArgumentParser(); ap.add_argument('-g', default='mine'); ap.add_argument('-n', default='2,3,4')
ap.add_argument('--min-papers', type=int, default=3); ap.add_argument('--top', type=int, default=200)
ap.add_argument('--openers', action='store_true'); ap.add_argument('--region', default='main,appendix,caption,statement')
ap.add_argument('--contains', default=None); ap.add_argument('--corpus', default=os.environ.get('STYLE_CORPUS', os.path.join('style_corpus','corpus.jsonl')))
a=ap.parse_args(); regions=set(a.region.split(','))
STOP=set('the a an of to in and or for on with by as at from is are be was were this that these those it its we our their which'.split())
rows=[json.loads(l) for l in open(a.corpus, encoding='utf-8')]
rows=[d for d in rows if d['group']==a.g and d['region'] in regions]
cnt=collections.Counter(); docs=collections.defaultdict(set)
for d in rows:
    t=re.sub(r'\[(CITE|REF|M|EQ)\]', lambda m: m.group(0), d['text'])
    toks=re.findall(r"\[(?:CITE|REF|M|EQ)\]|[A-Za-z][A-Za-z'\-]*|\d+(?:\.\d+)?%?|[,;:()]", t)
    if a.openers:
        for n in (1,2,3,4):
            g=' '.join(toks[:n]); cnt[g]+=1; docs[g].add(d['paper'])
        continue
    for n in map(int,a.n.split(',')):
        for i in range(len(toks)-n+1):
            g=toks[i:i+n]
            if all(x.lower() in STOP or not x[0].isalpha() for x in g): continue
            if g[0] in ',;:)' or g[-1] in ',;:(' : continue
            s=' '.join(g)
            if a.contains and a.contains.lower() not in s.lower(): continue
            cnt[s.lower()]+=1; docs[s.lower()].add(d['paper'])
items=[(k,v,len(docs[k])) for k,v in cnt.items() if len(docs[k])>=a.min_papers]
items.sort(key=lambda x:(-x[2],-x[1]))
for k,v,p in items[:a.top]: print(f'{p}p {v:4d}  {k}')
