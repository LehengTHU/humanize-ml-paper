#!/usr/bin/env python3
"""Phrase search: the skill's shipped phrase index by default, or your own sentence corpus.
usage: ps.py PHRASE [PHRASE2 ...] [-g house,refA,refB] [-q]
             [--corpus DIR/corpus.jsonl] [-r] [--region main,...] [-n 3] [--draft main.tex] [--recent-years 3]
  PHRASE     a plain phrase of 1-5 words (case-insensitive, word-boundary; '*' matches exactly
             one word, e.g. "we * that"). With --corpus you also get a regex (-r) and '...'
             (any words); without it the shipped index only understands plain phrases.
  --corpus   query your own corpus.jsonl (built with build_corpus.py) instead of the shipped
             index; falls back to $STYLE_CORPUS, else ./style_corpus/corpus.jsonl, else the index
  -g         groups to report; default 'house,refA,refB' against the index, 'mine,reference'
             against a corpus ('draft' is added automatically by --draft)
  -q         counts only (no examples / no per-paper table row breakdown beyond totals)
  -n         examples per group, corpus mode only (default 3); the shipped index has no example
             text (only counts), so -n and --region are ignored in index mode
  --region   regions to count, corpus mode only (default main,appendix,caption,statement)
  --draft    corpus mode only: a paper's main .tex, split into sentences on the fly as group
             'draft' (never written anywhere)
  --recent-years  corpus mode only: papers of 'mine' within this many years of the newest one
             count as recent (default 3)

Index mode prints, per group: total occurrences, how many of the group's papers contain it, and
the per-paper counts; for 'house' also the tier: core = phrase used in >= 2 of the 5 most recent
house papers (H2-H6); occasional = 1; retired = only in the older house paper (H1); ref_only =
0 in house but used in >= 2 reference (refA+refB) papers combined; absent = nowhere. 'banned' is
not detected from counts alone -- check references/prose.md "Habits to avoid" and the lexicon's
banned tier for that.

Corpus mode (your own papers) prints the same shape of numbers plus example sentences with
file:line, and its own tier rule (core/occasional/retired/reference only/absent) using
--recent-years. See tools/README.md for both modes."""
import argparse, collections, gzip, json, os, re, sys

here = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('phrases', nargs='+')
ap.add_argument('-r', action='store_true', help='regex; needs --corpus')
ap.add_argument('-g', default=None)
ap.add_argument('--region', default='main,appendix,caption,statement')
ap.add_argument('-n', type=int, default=3)
ap.add_argument('-q', action='store_true')
ap.add_argument('--corpus', default=os.environ.get('STYLE_CORPUS', os.path.join('style_corpus', 'corpus.jsonl')))
ap.add_argument('--index', default=os.path.join(here, 'phrase_index.json.gz'))
ap.add_argument('--draft', default=None)
ap.add_argument('--recent-years', type=int, default=3)
a = ap.parse_args()

use_corpus = os.path.isfile(a.corpus)
if a.r and not use_corpus:
    sys.exit(f'-r (regex) needs --corpus (corpus not found: {a.corpus})')
if a.draft and not use_corpus:
    sys.exit(f'--draft needs --corpus (corpus not found: {a.corpus})')

# ---------------------------------------------------------------- index mode
if not use_corpus:
    if not os.path.isfile(a.index):
        sys.exit(f'no corpus at {a.corpus} and no phrase index at {a.index}; '
                 f'pass --corpus, or build one with tools/build_corpus.py')
    data = json.load(gzip.open(a.index, 'rt', encoding='utf-8'))
    meta, ngrams = data['meta'], data['ngrams']
    group_papers = meta['groups']  # {'house': [...], 'refA': [...], 'refB': [...]}
    house_current = set(meta.get('house_current', []))
    groups = (a.g or 'house,refA,refB').split(',')
    ALL_GROUPS = list(group_papers.keys())

    def match(phrase):
        toks = phrase.strip().lower().split()
        n = len(toks)
        if n < 1 or n > 5:
            return n, {}
        table = ngrams.get(str(n), {})
        if '*' not in toks:
            hit = table.get(' '.join(toks))
            return n, (dict(hit) if hit else {})
        pat = re.compile('^' + r'\ '.join(r"[a-z']+" if t == '*' else re.escape(t) for t in toks) + '$')
        merged = collections.Counter()
        for gram, per in table.items():
            if pat.match(gram):
                merged.update(per)
        return n, dict(merged)

    for p in a.phrases:
        print(f'=== "{p}"')
        n, per_paper = match(p)
        if n > 5:
            print('  (skipped: the shipped index only covers phrases up to 5 words; '
                  'build your own corpus with tools/build_corpus.py for longer patterns)')
            continue
        if n < 1:
            print('  (empty phrase)')
            continue
        by_group = {g: collections.Counter({k: v for k, v in per_paper.items() if k in group_papers.get(g, [])})
                    for g in ALL_GROUPS}
        for g in groups:
            if g not in group_papers:
                print(f'  {g}: unknown group (known: {", ".join(ALL_GROUPS)})')
                continue
            counter = by_group[g]
            tot = sum(counter.values())
            gp = group_papers[g]
            detail = ' '.join(f'{k}:{counter[k]}' for k in gp if counter[k])
            print(f'  {g:6s} total {tot:3d} | papers {len(counter)}/{len(gp)} | {detail}')
        if 'house' in group_papers:
            hc = by_group['house']
            nr = len([k for k in hc if k in house_current])
            ref_papers = len(by_group.get('refA', {})) + len(by_group.get('refB', {}))
            tier = ('core' if nr >= 2 else 'occasional' if nr == 1 else 'retired' if hc else
                    'ref_only' if ref_papers >= 2 else 'absent')
            print(f'  tier (house): {tier}  ({nr} of {len(house_current)} current house papers)')
    sys.exit(0)

# ---------------------------------------------------------------- corpus mode (your own papers)
rows = [json.loads(l) for l in open(a.corpus, encoding='utf-8')]
if a.draft:
    sys.path.insert(0, here)
    from build_corpus import paper_sentences
    rows += paper_sentences('DRAFT', 'draft', 0, os.path.abspath(a.draft))
    a.g = (a.g or 'mine,reference')
    if 'draft' not in a.g.split(','):
        a.g += ',draft'
groups = (a.g or 'mine,reference').split(',')
regions = set(a.region.split(','))
PAPERS = collections.OrderedDict()
YEAR = {}
for d in rows:
    PAPERS.setdefault(d['group'], [])
    if d['paper'] not in PAPERS[d['group']]:
        PAPERS[d['group']].append(d['paper'])
        YEAR[d['paper']] = d.get('year', 0)
mine_years = [YEAR[p] for p in PAPERS.get('mine', []) if YEAR[p]]
newest = max(mine_years) if mine_years else 0
recent = {p for p in PAPERS.get('mine', []) if not newest or not YEAR[p] or YEAR[p] > newest - a.recent_years}
words = collections.Counter()
for d in rows:
    if d['region'] in regions:
        words[d['group']] += len(d['text'].split())


def compile_p(p):
    if a.r:
        return re.compile(p, re.I)
    toks = []
    for t in p.split():
        if t == '*':
            toks.append(r"[\w'\-]+")
        elif t == '...':
            toks.append(r".{0,80}?")
        else:
            toks.append(re.escape(t))
    body = r'\s+'.join(toks)
    pre = r'\b' if re.match(r'\w', p) else ''
    post = r'\b' if re.search(r'\w$', p) else ''
    return re.compile(pre + body + post, re.I)


for p in a.phrases:
    rx = compile_p(p)
    print(f'=== "{p}"')
    found = {}
    for g in groups:
        per = collections.Counter()
        ex = []
        for d in rows:
            if d['group'] != g or d['region'] not in regions:
                continue
            ms = rx.findall(d['text'])
            if ms:
                per[d['paper']] += len(ms)
                if len(ex) < a.n:
                    ex.append(d)
        found[g] = per
        tot = sum(per.values())
        n = len(PAPERS.get(g, []))
        rate = 1000 * tot / max(1, words[g])
        detail = ' '.join(f'{k}:{per[k]}' for k in PAPERS.get(g, []) if per[k])
        print(f'  {g:9s} total {tot:3d} | papers {len(per)}/{n} | {rate:.2f}/1k | {detail}')
        if not a.q:
            for d in ex:
                t = d['text']
                m = rx.search(t)
                s = max(0, m.start() - 70)
                e = min(len(t), m.end() + 70)
                print(f'      [{d["paper"]} {d["region"]} {d["file"]}:{d["line"]}] ...{t[s:e]}...')
    if 'mine' in PAPERS:
        per = found.get('mine') or collections.Counter()
        nr = len([k for k in per if k in recent])
        tier = ('core' if nr >= 2 else 'occasional' if nr == 1 else 'retired' if per else
                'reference only' if found.get('reference') else 'absent')
        print(f'  tier (mine): {tier}  ({nr} of {len(recent)} recent papers)')
