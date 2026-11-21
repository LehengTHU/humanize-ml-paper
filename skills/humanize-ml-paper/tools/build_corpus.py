#!/usr/bin/env python3
"""Build a sentence corpus from YOUR OWN LaTeX sources, for tools/ps.py and tools/ngrams.py.

usage:
  build_corpus.py --mine a/main.tex[::YEAR] b/main.tex[::YEAR] ... [--reference x/main.tex[::YEAR] ...]
                  --out DIR [--wrappers coA,coB]
  build_corpus.py --config my_sources.json --out DIR
    my_sources.json: {"papers": [{"key": "A", "group": "mine", "year": 2026, "path": "a/main.tex"}, ...]}
                     (paths relative to the JSON file; groups: mine / reference)

Each path is the main .tex of one paper (the file with \\begin{document}); \\input / \\include files are
followed. --wrappers lists extra one-argument revision macros whose text should be kept (e.g. co-author
edit macros). Writes DIR/corpus.jsonl (one sentence per row: paper, group, year, region = main / appendix /
caption / statement, section, file, line, text; math -> [M] / [EQ], citations -> [CITE], refs -> [REF]) and
DIR/vocab.txt (lower-case words of the 'mine' main text, usable as check_paper.py --vocab).
DIR must be outside the skill folder: the corpus holds your sentences and is never shipped with the skill.
Stdlib only.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
EXTRA_WRAPPERS = "coA|coB"          # extended by --wrappers


def strip_comment(l):
    out = ''; i = 0
    while i < len(l):
        c = l[i]
        if c == '\\' and i + 1 < len(l): out += l[i:i + 2]; i += 2; continue
        if c == '%': break
        out += c; i += 1
    return out


def expand(path, seen=None, depth=0):
    seen = seen or set()
    if depth > 6 or path in seen or not os.path.exists(path): return []
    seen.add(path); d = os.path.dirname(path); res = []
    with open(path, encoding='utf-8', errors='ignore') as fh:
        for n, raw in enumerate(fh, 1):
            l = strip_comment(raw.rstrip('\n'))
            m = re.search(r'\\(input|include)\{([^}]+)\}', l)
            if m:
                pre = l[:m.start()]
                if pre.strip(): res.append((path, n, pre))
                f = m.group(2).strip()
                for c in [os.path.join(d, f), os.path.join(d, f + '.tex')]:
                    if os.path.isfile(c): res += expand(c, seen, depth + 1); break
                post = l[m.end():]
                if post.strip(): res.append((path, n, post))
            else:
                res.append((path, n, l))
    return res


MACROS = {r'\ie': 'i.e.', r'\eg': 'e.g.', r'\wrt': 'w.r.t.', r'\cf': 'cf.', r'\etal': 'et al.', r'\aka': 'a.k.a.',
          r'\vs': 'vs.', r'\etc': 'etc.', r'\iid': 'i.i.d.'}
MATH_ENVS = 'equation|equation\\*|align|align\\*|gather|gather\\*|multline|multline\\*|eqnarray|eqnarray\\*|displaymath|split|alignat|alignat\\*|flalign|flalign\\*'
DROP_ENVS = 'tabular|tabular\\*|tabularx|algorithmic|algorithm|algorithm2e|tikzpicture|lstlisting|verbatim|minted|thebibliography|comment|axis'


def arg_text(s):
    # replace \cmd[opt]{arg} keeping arg for formatting commands
    for _ in range(4):
        s = re.sub(r'\\(textbf|textit|emph|underline|textsc|texttt|textrm|textsf|mbox|text|concept|hl|revise|new|red|blue|textcolor\{[^}]*\}|footnotesize|small|mathrm|' + EXTRA_WRAPPERS + r')\*?\s*\{([^{}]*)\}', r'\2', s)
    return s


def clean(t):
    t = re.sub(r'\\begin\{(' + MATH_ENVS + r')\}.*?\\end\{\1\}', ' [EQ] ', t, flags=re.S)
    t = re.sub(r'\\\[.*?\\\]', ' [EQ] ', t, flags=re.S)
    t = re.sub(r'\$\$.*?\$\$', ' [EQ] ', t, flags=re.S)
    t = re.sub(r'\\begin\{(' + DROP_ENVS + r')\}.*?\\end\{\1\}', ' ', t, flags=re.S)
    t = re.sub(r'(?<!\\)\$[^$]*?(?<!\\)\$', ' [M] ', t, flags=re.S)
    t = re.sub(r'\\\(.*?\\\)', ' [M] ', t, flags=re.S)
    t = re.sub(r'\\(cite[pt]?|citet|citep|citealp|citeauthor|citeyear|shortcite)\*?(\[[^\]]*\])*\{[^}]*\}', '[CITE]', t)
    t = re.sub(r'\\(ref|cref|Cref|eqref|autoref|pageref|nameref)\{[^}]*\}', '[REF]', t)
    t = re.sub(r'\\(label|vspace|hspace|includegraphics|url|href|footnote|centering|resizebox|setlength|addtolength|renewcommand|newcommand|def|bibliographystyle|bibliography)\*?(\[[^\]]*\])*(\{[^{}]*\})*', ' ', t)
    for k, v in MACROS.items(): t = re.sub(re.escape(k) + r'(?![A-Za-z])\{?\}?', v, t)
    t = arg_text(t)
    t = re.sub(r'\\(begin|end)\{[^}]*\}(\[[^\]]*\])?(\{[^}]*\})?', ' ', t)
    t = re.sub(r'\\item(\[[^\]]*\])?', ' \x03 ', t)   # item boundary
    t = re.sub(r'\\(paragraph|subsubsection)\*?\{([^}]*)\}', lambda m: ' \x03 ' + m.group(2) + '. ', t)
    t = re.sub(r'\\[a-zA-Z@]+\*?', ' ', t)
    t = re.sub(r'[{}]', '', t)
    t = t.replace('~', ' ').replace('``', '"').replace("''", '"').replace('\\%', '%').replace('\\&', '&').replace('\\_', '_').replace('---', ' --- ').replace('--', '-')
    t = re.sub(r'\\', ' ', t)
    return t


ABBR = ['i.e.', 'e.g.', 'et al.', 'w.r.t.', 'cf.', 'a.k.a.', 'vs.', 'etc.', 'Fig.', 'Figs.', 'Eq.', 'Eqs.', 'Sec.', 'Tab.', 'No.',
        'resp.', 'approx.', 'i.i.d.', 'St.', 'Appx.', 'App.', 'Thm.', 'Prop.', 'Def.', 'Lem.', 'Cor.']


def split_sents(t):
    prot = t
    for a in ABBR: prot = prot.replace(a, a.replace('.', '\x04'))
    prot = re.sub(r'(\d)\.(\d)', lambda m: m.group(1) + '\x04' + m.group(2), prot)
    parts = re.split(r'(?<=[.!?])\s+(?=["(\[]?[A-Z\x01])|\x03', prot)
    return [p.replace('\x04', '.') for p in parts]


def paper_sentences(key, group, year, main):
    """All sentences of one paper (main .tex path, \\input files followed) as corpus rows."""
    lines = expand(main)
    region = 'main'; section = ''; buf = []
    blocks = []  # (region, section, text-with-markers)

    def flush():
        if buf: blocks.append((region, section, '\n'.join(buf))); buf.clear()
    started = not any(re.search(r'\\begin\{document\}', x[2]) for x in lines)
    for f, n, l in lines:
        if not started:
            if re.search(r'\\begin\{document\}', l): started = True
            continue
        if re.search(r'\\end\{document\}', l):
            break
        if re.search(r'\\(bibliography|printbibliography|bibliographystyle)\b', l):
            continue
        if re.search(r'\\appendix\b', l) or re.search(r'\\begin\{appendices\}', l):
            flush(); region = 'appendix'
        m = re.search(r'\\(section|subsection)\*?\{(.*)\}', l)
        if m and m.group(1) == 'section':
            flush(); section = re.sub(r'\\[a-zA-Z]+|[{}]', '', m.group(2))[:60]
        if re.search(r'\\section\*?\{\s*(Impact Statement|Broader Impact|Ethics|Reproducibility|Acknowledg)', l, re.I):
            flush(); region = 'statement'
        buf.append(f'\x01{os.path.relpath(f, os.path.dirname(main))}:{n}\x02' + l)
    flush()
    rows = []
    for region_, section_, txt in blocks:
        caps = []
        res = ''; i = 0            # extract \caption{...} with nested braces
        while True:
            j = txt.find('\\caption', i)
            if j < 0: res += txt[i:]; break
            res += txt[i:j]; k = txt.find('{', j)
            if k < 0: res += txt[j:]; break
            depth = 0; e = k
            while e < len(txt):
                if txt[e] == '{': depth += 1
                elif txt[e] == '}':
                    depth -= 1
                    if depth == 0: break
                e += 1
            mk = txt.rfind('\x01', 0, j); mk_s = txt[mk:txt.find('\x02', mk) + 1] if mk >= 0 else ''
            caps.append(mk_s + txt[k + 1:e]); i = e + 1
        for reg, body in [(region_, res)] + [('caption', c) for c in caps]:
            ct = clean(body)
            cur = None
            for s in split_sents(ct):
                ms = re.findall(r'\x01([^\x02]*)\x02', s)
                if ms:
                    if s.split('\x01')[0].strip() == '': cur = ms[0]
                    last = ms[-1]
                else: last = None
                loc = cur
                s2 = re.sub(r'\x01[^\x02]*\x02', ' ', s)
                s2 = re.sub(r'\s+', ' ', s2).strip()
                if last: cur = last
                if len(re.findall(r'[A-Za-z]{2,}', s2)) < 3: continue
                fl = (loc or ':').rsplit(':', 1)
                rows.append({'paper': key, 'group': group, 'year': year, 'region': reg, 'section': section_,
                             'file': fl[0], 'line': int(fl[1]) if fl[1].isdigit() else 0, 'text': s2})
    return rows


def _parse(spec, group):
    path, _, year = spec.partition("::")
    key = os.path.basename(os.path.dirname(os.path.abspath(path))) or os.path.splitext(os.path.basename(path))[0]
    return {"key": key, "group": group, "year": int(year) if year.isdigit() else 0, "path": os.path.abspath(path)}


def main():
    global EXTRA_WRAPPERS
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mine", nargs="*", default=[], metavar="TEX[::YEAR]")
    ap.add_argument("--reference", nargs="*", default=[], metavar="TEX[::YEAR]")
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", required=True, help="output directory (outside the skill folder)")
    ap.add_argument("--wrappers", default="", help="comma-separated extra macro names whose argument is kept")
    a = ap.parse_args()
    out_dir = os.path.abspath(a.out)
    if os.path.commonpath([out_dir, SKILL_ROOT]) == SKILL_ROOT:
        sys.exit(f"refusing to write inside the skill folder ({SKILL_ROOT}); pass --out in your own workspace")
    if a.wrappers:
        EXTRA_WRAPPERS += "|" + "|".join(re.escape(w.strip().lstrip("\\")) for w in a.wrappers.split(",") if w.strip())
    papers = [_parse(p, "mine") for p in a.mine] + [_parse(p, "reference") for p in a.reference]
    if a.config:
        cfg = json.load(open(a.config, encoding="utf-8"))
        base = os.path.dirname(os.path.abspath(a.config))
        for p in cfg["papers"]:
            papers.append({"key": p["key"], "group": p.get("group", "mine"), "year": int(p.get("year", 0)),
                           "path": os.path.join(base, p["path"])})
    if not papers:
        sys.exit("no papers: pass --mine TEX ... and/or --config FILE")
    keys = [p["key"] for p in papers]
    for i, p in enumerate(papers):                  # make keys unique (two papers named main/)
        if keys.count(p["key"]) > 1:
            p["key"] = f"{p['key']}{i + 1}"
    missing = [p["path"] for p in papers if not os.path.isfile(p["path"])]
    if missing:
        sys.exit(f"not found: {missing}")
    os.makedirs(out_dir, exist_ok=True)
    stats, vocab = {}, set()
    with open(os.path.join(out_dir, "corpus.jsonl"), "w", encoding="utf-8") as out:
        for p in papers:
            rows = paper_sentences(p["key"], p["group"], p["year"], p["path"])
            for r in rows:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                if r["group"] == "mine" and r["region"] == "main":
                    vocab.update(w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'\-]*[A-Za-z]", r["text"]))
            stats[p["key"]] = (p["group"], p["year"], len(rows))
    with open(os.path.join(out_dir, "vocab.txt"), "w", encoding="utf-8") as fh:
        fh.write("# lower-case words of the 'mine' main text (build_corpus.py); use with check_paper.py --vocab\n")
        fh.write("\n".join(sorted(vocab)) + "\n")
    for k, (g, y, n) in stats.items():
        print(f"  {k:20s} {g:9s} {y or '-':>5}  {n} sentences")
    print(f"wrote {os.path.join(out_dir, 'corpus.jsonl')} and vocab.txt ({len(vocab)} words)")


if __name__ == "__main__":
    main()
