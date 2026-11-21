#!/usr/bin/env python3
"""check_paper.py -- budget, page, venue and style lint for a paper in the house layout.

Usage:
    python3 check_paper.py <paper_dir> [--venue iclr|neurips|icml] [--stage submission|camera]
                           [--limit N] [--aux main.aux] [--vocab PATH] [--habits-max N]

Reports
  1. prose words per chapter vs the venue blueprint (references/structure.md section 5);
     floats, display math and comments are stripped, inline math counts as one word;
     only the chapter files the main .tex really \\input (superseded drafts are ignored);
  2. the page of \\label{main-text-end} from the .aux (build with
     `tectonic -X compile --keep-intermediates main.tex`); it must EQUAL the page limit
     of the venue AND stage (submission vs camera-ready);
  3. venue checks: style-kit year, required statements / checklist, anonymity at submission,
     column-specific float rules (ICML), citation command, bibliography style;
  4. concepts: count of core/framing concepts and marked uses, placement (Introduction + first
     formal definition), one key = one phrase (references/concepts.md);
  4b. terms: every '% concept:' / '% term:' row carries its source (borrowed: citekey + quote,
     composed: citekeys, plain, coined <= 2), '(termed X)' phrases have a row, and known
     sense-clash words in the live text (probe/probing, pre-registration, seed noise, ...);
  5. vocabulary: hyphenated-compound rate, one-off compounds and, when --vocab PATH is given, long
     low-frequency words outside that reference word list (prose.md "Plain words, no coinage");
  6. lint hits: leftover placeholders, banned words, venue-specific mistakes;
  7. cohesion notes per main chapter (soft targets, not hits; prose.md section 4b): share of
     connective-led sentences and connectives per 100 words, double lock (connective + this/these/
     such), anaphor-led sentences, an approximate isolation rate, ", so" per 1k words, and the
     "(termed X)" count against the number of core concepts;
  8. intro & contributions (references/introduction.md, contributions.md): contribution-list phrasing,
     "novel" / "first" in abstract, intro and conclusion, "To the best of our knowledge", reference-style
     difference sentences, "is not our contribution", sentence-initial "Ideally,", "we argue", abstract and
     intro paragraphs ending on a reservation, the "% epithet: <phrase>" count in abstract / intro /
     Methodology opener / Conclusion, and strong result verbs while tables hold \\pend or '--' cells;
  9. habits: warnings with line numbers for the 27 recurring draft habits of prose.md "Habits to
     avoid" and the foreign connectives, each with a plain alternative (--habits-max N per habit);
  10. sentences (prose.md section 12): per chapter sentence length (mean, median, >35 / >45 words),
     parentheticals per sentence, two-main-clause sentences, 'Since' openers, This/These/Such openers and
     pointer endings against the source ranges, then line lists for rules SR2-SR15 (long sentences, long
     fronts, two subjects, mid-sentence 'which', our method in the 'while' clause, results hidden in a
     'Since' clause or a parenthesis, stacked tails, fragments, clefts).
Venue facts are the last verified values (see VENUES); limits change every year, so ALWAYS
re-check the current call for papers (venues.md section 1.0) and pass --limit when it differs.
Stdlib only.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

# Venue facts, LAST VERIFIED (venues.md section 1) against the official kits (ICLR 2026, NeurIPS 2025
# and 2026, ICML 2026) and, on 2026-09-25, the ICLR 2027 template + Author Guide, the NeurIPS 2026
# handbook and the ICML 2026 call. They change: ICLR 2025 allowed 10 pp
# at submission, ICLR 2026/2027 9 (+1 camera-ready); ICLR 2027 made an AI-use statement mandatory.
VENUES = {
    "iclr":    {"verified": 2027, "limit": {"submission": 9, "camera": 10}, "columns": 1,
                "sty": r"iclr(\d{4})_conference", "bst": r"iclr\d{4}_conference"},
    "neurips": {"verified": 2026, "limit": {"submission": 9, "camera": 10}, "columns": 1,
                "sty": r"neurips_(\d{4})", "bst": r"unsrtnat"},
    "icml":    {"verified": 2026, "limit": {"submission": 8, "camera": 9}, "columns": 2,
                "sty": r"icml(\d{4})", "bst": r"icml\d{4}"},
}
# prose-word ranges per chapter (structure.md blueprints A/B/C), SUBMISSION length.
# Abstract: at most 250 words [most]. Preferred 120-200 at ICML and NeurIPS [current] (ICML also asks
# for 4-6 sentences); ICLR only the 250 ceiling (no evidence for a stricter target).
BLUEPRINT = {
    "iclr":    {"abstract": (120, 250), "introduction": (650, 750), "preliminary": (350, 550),
                "methodology": (900, 1100), "experiments": (850, 1000), "conclusion": (115, 175),
                "total": (3500, 3700)},
    "neurips": {"abstract": (120, 250), "introduction": (650, 750), "preliminary": (400, 600),
                "methodology": (1000, 1300), "experiments": (950, 1150), "conclusion": (120, 150),
                "total": (3700, 3850)},
    # ICML two columns, 8 pp at submission [venue: ICML]: about 715 prose words per page with ~12
    # floats (~2.6 pp of floats) fill 8.0 pp in Times (venues.md sections 2.4 and 3.6).
    "icml":    {"abstract": (120, 250), "introduction": (750, 850), "preliminary": (550, 650),
                "methodology": (1000, 1150), "experiments": (900, 1000), "conclusion": (130, 150),
                "total": (3650, 3900)},
}
# camera-ready: +1 page in all three venues, but most of it goes to floats [most]. Prose totals
# when a paper fills the camera limit; the extra words go to the Experiments and Introduction.
CAMERA_TOTAL = {"iclr": (3600, 3900),      # 10 pp
                "neurips": (3750, 4150),   # 10 pp
                "icml": (3800, 4550)}      # 9 pp; a used 9th page adds ~600-700 words
                                           # or 2 column floats
CAMERA_EXTRA = {"experiments": 0.6, "introduction": 0.4}
TARGET = {"neurips": {"abstract": (120, 200)},   # preferred sub-range inside the accepted range
          "icml": {"abstract": (120, 200)}, "iclr": {}}
# never linted: the preamble defines \ie/\eg as \emph{i.e., } etc. (8 false "italic" hits otherwise);
# checklist.tex is the venue's own text (itemize, \emph in the questions): checked separately.
LINT_SKIP = {"preamble.tex", "math_commands.tex", "checklist.tex"}
KEYS = ["abstract", "introduction", "preliminary", "methodology", "experiments", "conclusion"]

BANNED = [r"\bdelve", r"\bfurnish", r"\belucidat", r"\bunderpin", r"\bde facto\b", r"\bWherein\b",
          r"\bSurprisingly\b", r"sheds? light on", r"unleash", r"\bWorse still\b",
          r"state-of-the-art", r"\bSOTA\b", r"To be specific", r"\bFurthermore\b", r"\bNotably\b",
          r"kindly refer", r"novelly", r"\bCodes\b", r"\bIt's\b", r"\% times",
          r"\balways\b", r"rest of (?:this|the) paper is organized"]
PLACEHOLDERS = [r"\\pend\b", r"\[Expected\]", r"\\figplaceholder", r"<[A-Za-z][^<>\n]{0,40}>",
                r"Placeholder-[ABC]"]


def uncomment(src: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", src)


def strip_tex(src: str) -> str:
    src = uncomment(src)                                                      # comments
    for env in ["figure\\*?", "table\\*?", "algorithm", "wrapfigure", "equation\\*?", "align\\*?",
                "gather\\*?", "tabular\\*?", "tabularx", "lrbox", "tcolorbox"]:
        src = re.sub(r"\\begin\{(%s)\}.*?\\end\{\1\}" % env, " ", src, flags=re.S)
    src = re.sub(r"\\\[.*?\\\]", " ", src, flags=re.S)                       # display math
    src = re.sub(r"\$[^$]*\$", " MATH ", src)                                # inline math = 1 token
    src = re.sub(r"\\(cite[pt]?|ref|eqref|Eqref|label|url|footnote|input|citeauthor|citeyear)\*?\{[^}]*\}", " ", src)
    src = re.sub(r"\\(section|subsection|subsubsection)\*?\{[^}]*\}", " ", src)
    src = re.sub(r"\\(begin|end)\{[^}]*\}(\[[^\]]*\])?", " ", src)
    src = re.sub(r"\\[A-Za-z@]+\*?", " ", src)                                # remaining commands
    src = re.sub(r"[{}\[\]~]", " ", src)
    return src


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", text))


def chapter_key(path: str) -> str | None:
    name = os.path.basename(path).lower()
    for k in KEYS:
        if k[:5] in name:
            return k
    if re.search(r"^\d+_pre(?:_|\.)", name):      # short names such as 2_pre.tex, 2_pre_<initials>.tex
        return "preliminary"
    return None


def read(path: str) -> str:
    return open(path, encoding="utf-8", errors="ignore").read()


def find_main(paper_dir: str) -> tuple[str | None, str, str | None, int | None, str]:
    """Main .tex = the file with \\documentclass and \\begin{document}; prefer one loading a venue kit.
    Returns (path, source, venue, kit year, package options)."""
    fallback = (None, "", None, None, "")
    for p in sorted(glob.glob(os.path.join(paper_dir, "*.tex"))):
        src = read(p)
        body = uncomment(src)
        if "\\documentclass" not in body or "\\begin{document}" not in body:
            continue
        for m in re.finditer(r"\\usepackage(\[[^\]]*\])?\{([^}]*)\}", body):
            for pkg in m.group(2).split(","):
                for v, info in VENUES.items():
                    mm = re.fullmatch(info["sty"], pkg.strip())
                    if mm:
                        return p, src, v, int(mm.group(1)), (m.group(1) or "")
        if fallback[0] is None:
            fallback = (p, src, None, None, "")
    return fallback


def expand(src: str, base: str, depth: int = 0) -> str:
    """Main source with every live \\input/\\include replaced by its (uncommented) content."""
    src = uncomment(src)
    if depth > 3:
        return src

    def sub(m: re.Match) -> str:
        name = m.group(1).strip()
        p = os.path.join(base, name if name.endswith(".tex") else name + ".tex")
        return expand(read(p), base, depth + 1) if os.path.exists(p) else " "
    return re.sub(r"\\(?:input|include)\{([^}]*)\}", sub, src)


def live_chapters(main_src: str, paper_dir: str) -> list[str]:
    """Chapter files the main .tex really \\inputs, in order (only these are the paper)."""
    out = []
    for name in re.findall(r"\\(?:input|include)\{([^}]*)\}", uncomment(main_src)):
        name = name.strip()
        p = os.path.join(paper_dir, name if name.endswith(".tex") else name + ".tex")
        if os.path.exists(p) and os.path.dirname(os.path.relpath(p, paper_dir)) == "chapters":
            out.append(p)
    return out


def envs(doc: str, name: str) -> list[str]:
    return re.findall(r"\\begin\{%s\}(.*?)\\end\{%s\}" % (name, name), doc, flags=re.S)


def venue_checks(venue: str, stage: str, year: int | None, opts: str, main_src: str,
                 doc: str, paper_dir: str) -> int:
    """Venue requirements (V) and venue-dependent style rules (S); see venues.md section 1."""
    hits = 0

    def hit(msg: str) -> None:
        nonlocal hits
        hits += 1
        print(f"  {msg}")

    info = VENUES[venue]
    if year is None:
        hit(f"no {venue} style kit found in the main .tex (\\usepackage{{{info['sty']}}})")
    elif year > info["verified"]:
        print(f"  NOTE: kit year {year} > last verified {info['verified']}: re-check page limit, statements "
              f"and checklist in the {year} call for papers (venues.md section 1.0); pass --limit N")
    bib = doc.find("\\bibliography{")
    apx = doc.find("\\appendix")
    main_part = doc[:apx] if apx >= 0 else doc[:bib] if bib >= 0 else doc
    bst = re.search(r"\\bibliographystyle\{([^}]*)\}", doc)
    if not bst or not re.fullmatch(info["bst"], bst.group(1)):
        hit(f"bibliography style {bst.group(1) if bst else 'missing'}; use {info['bst']} "
            f"(the {venue} kit / house style)")

    def before_bib(pat: str) -> bool:
        m = re.search(pat, doc)
        return bool(m) and (bib < 0 or m.start() < bib)

    if venue == "iclr":
        if not before_bib(r"\\section\*\{Ethics Statement\}"):
            print("  info: no Ethics Statement before the references (optional; house style writes one)")
        if not before_bib(r"\\section\*\{Reproducibility Statement\}"):
            print("  info: no Reproducibility Statement before the references (optional; house style writes one)")
        ai = r"\\(?:sub)*section\*?\{(?:AI [Uu]se [Ss]tatement|Use of (?:LLMs|Large Language Models))\}"
        if (year or 0) >= 2027:                   # 2027 template: required, before the references
            if not before_bib(ai):
                hit("no AI use statement before the references (ICLR 2027: required, not counted, <= 1 page)")
        elif (year or 0) == 2026 and not re.search(ai, doc):
            hit("no 'Use of LLMs' section (ICLR 2026 requirement; put it last in the appendix)")
        if stage == "submission" and "\\iclrfinalcopy" in uncomment(main_src).split("\\begin{document}")[0]:
            hit("\\iclrfinalcopy is active: de-anonymizes a submission")
    elif venue == "neurips":
        if not re.search(r"\\PassOptionsToPackage\{[^}]*numbers[^}]*\}\{natbib\}", uncomment(main_src)):
            hit("natbib without 'numbers': unsrtnat then prints [Doe et al., 2025] instead of [1]")
        ck = next((c for c in (os.path.join(paper_dir, "checklist.tex"),
                               os.path.join(paper_dir, "chapters", "checklist.tex")) if os.path.exists(c)), "")
        m = re.search(r"NeurIPS Paper Checklist", doc)
        if year and year < 2025:                  # in-PDF checklist: 2025 and 2026 kits
            print(f"  info: {year} kit: checklist rule not checked (verified for the 2025/2026 kits)")
        elif not m or (bib >= 0 and m.start() < bib):
            hit("no NeurIPS Paper Checklist after the references/appendix (missing checklist = desk reject)")
        if ck:
            c = uncomment(read(ck))
            q = len(re.findall(r"\\item\s*\{\\bf", c))
            a = len(re.findall(r"Answer:\s*\\answer(?:Yes|No|NA)\{\}", c))
            todo = len(re.findall(r"\\answerTODO|\[TODO\]", c))
            if todo or a != q:
                hit(f"checklist: {q} questions, {a} answers, {todo} TODO left")
        if not re.search(r"\\section\*?\{Broader Impacts?\}", doc):
            print("  info: no Broader Impacts section (checklist Q10; house style: an appendix section)")
        if not re.search(r"\\section\*?\{Asset Licen[cs]es\}", doc):
            print("  info: no Asset Licenses section (checklist Q12; house style: an appendix table)")
        if stage == "submission":
            if re.search(r"final|preprint|nonanonymous", opts):
                hit(f"{opts} at submission: de-anonymizes and drops line numbers (omit final/preprint)")
            if re.search(r"\\begin\{ack\}", doc):
                hit("ack environment present at submission (neurips sty does not hide it)")
        elif year and year >= 2026 and not re.search(r"main|position|eandd|creativeai|workshop", opts):
            hit("camera-ready needs a track option, e.g. [main,final]; [final] alone stops at \\@trackname")
    elif venue == "icml":
        if not before_bib(r"\\section\*\{Impact Statement\}"):
            hit("no \\section*{Impact Statement} before the references (required, does not count)")
        if "\\printAffiliationsAndNotice" not in uncomment(main_src):
            hit("\\printAffiliationsAndNotice{} missing (required even if empty)")
        for _ in envs(main_part, r"wrapfigure"):
            hit("wrapfigure in the two-column main text: use figure[t] at \\columnwidth")
        for kind in ("figure", "table"):
            for body in envs(main_part, kind):
                if "\\textwidth" in body:
                    hit(f"\\textwidth inside a one-column {kind} (6.75 in, overflows): use \\columnwidth")
        for m in re.finditer(r"\\begin\{(figure|table)\*\}\[(!?[hbH])", main_part):
            hit(f"{m.group(1)}*[{m.group(2)}]: two-column floats go at the top of a page ([t])")
        ab = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", doc, flags=re.S)
        if ab:
            n = len([s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\\])", strip_tex(ab.group(1)).strip())
                     if len(s.split()) > 2])
            if not 4 <= n <= 6:
                hit(f"abstract has {n} sentences; ICML asks for roughly 4-6")
        if apx >= 0 and "\\onecolumn" not in doc[apx:apx + 400]:
            print("  info: appendix without \\onecolumn (house style: a one-column appendix)")
        nv = len(re.findall(r"\\vspace\{-", main_part))
        if nv:
            print(f"  info: {nv} negative \\vspace in the main text; ICML forbids compressing vertical "
                  "spaces: keep them inside floats only")
        if stage == "submission":
            if "accepted" in opts:
                hit("[accepted] option at submission: prints the author names")
            if before_bib(r"\\section\*\{Acknowledge?ments?\}"):
                hit("acknowledgements at submission (ICML: omit until camera-ready)")
    if stage == "submission":
        for m in re.finditer(r"(?i)our (?:code|codes|implementation)[^.\n]{0,80}\\url\{(?!https?://anonymous)([^}]*)\}", doc):
            hit(f"non-anonymous code link at submission: {m.group(1)} (use an anonymous link, e.g. anonymous.4open.science)")
        for m in re.finditer(r"(?i)\bour (?:previous|prior|earlier) (?:work|paper|study)", doc):
            hit(f"self-citation in the first person: '{m.group(0)}' (cite yourself in the third person)")
    return hits


# ----------------------------------------------------------------------------- concepts
# references/concepts.md -- 2-5 core concepts (max 6) + <= 6 framing terms, each declared once in a
# "% concept: phrase | core/framing | provenance | definition" table line and marked with the one-colour
# \concept{phrase}; 8-15 marked uses (cap 20), <= 12 distinct phrases, Introduction + first formal
# definition (Preliminary / Methodology) only; one concept = one phrase; never bold/italic on top;
# core concepts echoed (unmarked) after the Introduction.
CONCEPT_ALLOWED = {"introduction", "preliminary", "methodology"}
_ARG = r"\{((?:[^{}]|\{[^{}]*\})*)\}"


def live_files(path: str, base: str, depth: int = 0) -> list[str]:
    """The main file plus every file it \\inputs, recursively, in order."""
    out = [path]
    if depth > 4:
        return out
    for name in re.findall(r"\\(?:input|include)\{([^}]*)\}", uncomment(read(path))):
        q = os.path.join(base, name.strip() if name.strip().endswith(".tex") else name.strip() + ".tex")
        if os.path.exists(q) and q not in out:
            out += [f for f in live_files(q, base, depth + 1) if f not in out]
    return out


def _norm(phrase: str) -> str:
    t = re.sub(r"\$[^$]*\$", "", phrase)
    t = re.sub(r"\\[A-Za-z]+\*?", " ", t)
    t = re.sub(r"[{}~()`'\".,;:]", " ", t).lower()
    t = " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in t.split())
    return t


def concept_checks(main_path: str | None, paper_dir: str, stage: str) -> int:
    """Concept table ("% concept: phrase | core/framing | provenance | definition"), \concept{} marks,
    budget, placement and echo of core concepts (references/concepts.md)."""
    if not main_path:
        print("  no main .tex; skipped"); return 0
    files = live_files(main_path, paper_dir)
    declared: dict[str, tuple[str, str]] = {}   # norm phrase -> (kind, provenance)
    for f in files:
        for m in re.finditer(r"^\s*%\s*concept:\s*([^|\n]+)\|\s*(core|framing)\s*\|([^|\n]*)", read(f), flags=re.M):
            declared[_norm(m.group(1))] = (m.group(2), m.group(3).strip())
    marks = []                                    # (norm phrase, raw, relpath, line, chapter key)
    styled = 0
    body_by_file = {}
    for f in files:
        raw = uncomment(read(f))
        if os.path.basename(f) in LINT_SKIP:
            continue
        if f == main_path:
            head, sep, tail = raw.partition("\\begin{document}")
            raw = "\n" * head.count("\n") + sep + tail if sep else raw
        body_by_file[f] = raw
        ck = chapter_key(f) if f != main_path else None
        for m in re.finditer(r"(?<![A-Za-z@])\\concept" + _ARG, raw):
            if raw[max(0, m.start() - 12):m.start()].endswith("newcommand{"):
                continue
            marks.append((_norm(m.group(1)), m.group(1), os.path.relpath(f, paper_dir), raw.count("\n", 0, m.start()) + 1, ck))
        for m in re.finditer(r"\\text(?:bf|it)\{\s*\\concept\{|\\emph\{\s*\\concept\{|\\concept\{\s*\\(?:textbf|textit|emph)\{", raw):
            print(f"  {os.path.relpath(f, paper_dir)}:{raw.count(chr(10), 0, m.start()) + 1}: concept + bold/italic: colour is the only marker [all]")
            styled += 1
    if re.search(r"\\cpt\{|\\defconcept\{", "".join(uncomment(read(f)) for f in files)):
        print("  note: \\cpt{}/\\defconcept{} are not defined in templates/preamble.tex; use one-colour \\concept{} + '% concept:' table lines")
    hits = styled
    n = len(marks)
    phrases = {ph for ph, *_ in marks}
    core = {ph for ph, (k, _) in declared.items() if k == "core"}
    framing = {ph for ph, (k, _) in declared.items() if k == "framing"}
    print(f"  concept table: {len(core)} core (target 2-5, max 6), {len(framing)} framing (max 6)"
          + ("" if declared else "  -- MISSING: add '% concept: phrase | core/framing | provenance | definition' lines"))
    print(f"  marked uses: {n} (target 8-15, cap 20); distinct marked phrases: {len(phrases)} (max 12)"
          + ("" if n <= 15 else ("  ABOVE TARGET" if n <= 20 else "  OVER CAP")))
    for cond, msg in [(not declared and n > 0, "no concept table"),
                      (len(core) > 6, "more than 6 core concepts: merge or demote"),
                      (len(framing) > 6, "more than 6 framing terms: unmark generic words"),
                      (len(phrases) > 12, "more than 12 distinct marked phrases"),
                      (n > 20, "more than 20 marked uses: mark first mention only")]:
        if cond:
            print(f"  BUDGET: {msg}"); hits += 1
    for ph, (k, prov) in sorted(declared.items()):
        if not prov:
            print(f"  concept '{ph}': provenance missing (borrowed: citekey + quote / composed: parts with citekeys / coined)"); hits += 1
    if declared:
        for ph in sorted(phrases - set(declared)):
            print(f"  '{ph}' is marked but not in the concept table (declare it or unmark it)"); hits += 1
        for ph in sorted(core - phrases):
            print(f"  core concept '{ph}' is declared but never marked at its first mention"); hits += 1
    counts: dict[str, int] = {}
    for ph, raw_ph, rel, line, ck in marks:
        counts[ph] = counts.get(ph, 0) + 1
        if ck not in CONCEPT_ALLOWED:
            print(f"  {rel}:{line}: marked in {ck or 'appendix/other'}: only Introduction + first formal definition: {raw_ph[:50]!r}")
            hits += 1
    for ph, c in sorted(counts.items()):
        if c > 2:
            print(f"  '{ph}' marked {c} times: mark the first mention (and at most one formal definition) only"); hits += 1
    # echo table: unmarked mentions of each core concept per section
    secs = ["introduction", "preliminary", "methodology", "experiments", "conclusion"]
    main_chapters = [f for f in live_chapters(read(main_path), paper_dir)
                     if not re.search(r"appendix", os.path.basename(f), re.I)]   # direct \\inputs = main text
    if core:
        print("  echo (mentions per section; core concepts must reappear after the Introduction):")
        print("    " + "concept".ljust(26) + "".join(k[:5].rjust(7) for k in secs))
        for ph in sorted(core):
            row, pat = {}, re.compile(r"(?<![A-Za-z0-9])" + r"\s+".join(re.escape(w) for w in ph.split())
                                      + r"s?(?![A-Za-z0-9])", re.I)      # lookarounds also match "<placeholder>" phrases
            for f in main_chapters:
                ck = chapter_key(f)
                if ck in secs and f in body_by_file:
                    txt = _norm(re.sub(r"\\concept" + _ARG, lambda m: m.group(1), body_by_file[f]))
                    row[ck] = row.get(ck, 0) + len(pat.findall(txt))
            print("    " + ph[:25].ljust(26) + "".join(str(row.get(k, 0)).rjust(7) for k in secs))
            later = sum(row.get(k, 0) for k in secs[2:])
            if later == 0:
                print(f"    NO ECHO: '{ph}' never reappears after the Introduction"); hits += 1
            else:
                for k in ("experiments", "conclusion"):
                    if row.get(k, 0) == 0:
                        print(f"    weak echo: '{ph}' is absent from the {k} (name it where it is tested / restate it)"); hits += 1
    main_body = uncomment(read(main_path)) + "".join(uncomment(read(f)) for f in files if os.path.basename(f) == "preamble.tex")
    if stage == "submission" and re.search(r"\\showconceptstrue", main_body) and not re.search(r"\\showconceptsfalse", main_body):
        print("  note: concept colour is ON (drafting default); set \\showconceptsfalse for the submitted PDF")
    return hits


# ----------------------------------------------------------------------------- terms (provenance)
# references/concepts.md section 3 (term table): every key term carries its source from the CITED FIELD
# LITERATURE, same sense. A "fixed" term is only frozen in wording; it is not thereby verified.
#   % concept: phrase | core/framing | borrowed: citekey "quote <= 15 words" / composed: part (citekey) + part / coined | definition
#   % term:    phrase | borrowed: citekey "quote" / composed: ... / plain / coined | definition [| other senses: ...]
# Citation keys are looked up in the paper's .bib (short-name keys count too); without a
# .bib, author-year keys (na2024scalable) or \cite{} count. Coined rows (concepts + terms) above 2 warn.
TERM_VERDICTS = ("borrowed", "composed", "plain", "coined")
TERM_COINED_MAX = 2
_AUTHOR_YEAR = re.compile(r"^[A-Za-z][A-Za-z\-]*(?:19|20)\d\d[A-Za-z0-9\-]*$")
_QUOTE = re.compile(r"\"([^\"]{2,})\"|``(.{2,}?)''|“([^”]{2,})”|(<quote[^>]*>)")
# (pattern, hint, context that makes the word fine when found within +-60 characters on the same line)
SENSE_CLASH = [
    (r"\bprob(?:e|es|ed|ing)\b",
     "probe/probing = linear probe (classifier on hidden states) or knowledge probing in LLM work; "
     "for a test run write run / test / proxy / method",
     r"linear|logistic|classifier|knowledge|activ[a]tions?|representation|hidden state|probing task"),
    (r"\bpre-?regist",
     "pre-registration = a time-stamped protocol filed before any experiment; without a dated record "
     "write 'fixed in advance' / 'criteria fixed in advance'", None),
    (r"\bseed[- ]noise\b|\bseed-to-seed\b",
     "seed noise usually means initialization-seed noise; if only the data order varies, write "
     "run-to-run variation (or data-order noise)", None),
    (r"\bshare-aware\b",
     "share-aware = awareness of sharing (HCI / systems); say what the step does", None),
    (r"\bbase (?:update|delta|vector)s?\b",
     "'base' names the base model in merging papers; name the data the update was trained on", None),
]
_KEYARG = re.compile(r"\\(?:cite[a-z]*|[cC]?ref|eqref|autoref|label|input|include|includegraphics|url|href)"
                     r"\*?(?:\[[^\]]*\])*\{[^}]*\}")


def _bib_keys(paper_dir: str) -> set[str]:
    keys: set[str] = set()
    for b in glob.glob(os.path.join(paper_dir, "*.bib")):
        keys.update(k.strip() for k in re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", read(b)))
    return keys


def _table_rows(main_path: str, paper_dir: str) -> list[tuple[str, str, str, str, int]]:
    """(kind, phrase, provenance, relpath, line) for every '% concept:' and '% term:' line."""
    rows = []
    for f in live_files(main_path, paper_dir):
        src = read(f)
        for m in re.finditer(r"^[ \t]*%[ \t]*(concept|term):[ \t]*(.*)$", src, flags=re.M):
            fields = [x.strip() for x in m.group(2).split("|")]
            if m.group(1) == "concept":
                if len(fields) < 3 or fields[1] not in ("core", "framing"):
                    continue                      # malformed concept lines are reported by == concepts
                phrase, prov = fields[0], fields[2]
            else:
                phrase, prov = fields[0], (fields[1] if len(fields) > 1 else "")
            rows.append((m.group(1), phrase, prov, os.path.relpath(f, paper_dir), src.count("\n", 0, m.start()) + 1))
    return rows


def term_checks(main_path: str | None, paper_dir: str, chapters: list[str], cap: int) -> int:
    if not main_path:
        print("  no main .tex; skipped"); return 0
    warn = 0
    bib = _bib_keys(paper_dir)
    rows = _table_rows(main_path, paper_dir)
    tally = {v: 0 for v in TERM_VERDICTS}
    coined = []
    for kind, phrase, prov, rel, line in rows:
        where = f"{rel}:{line}: {kind} '{phrase}'"
        verdict = (re.match(r"\s*([A-Za-z]+)", prov) or [None, ""])[1].lower()
        if verdict not in TERM_VERDICTS:
            print(f"  {where}: provenance must start with borrowed / composed / plain / coined (got {prov[:40]!r})")
            warn += 1; continue
        tally[verdict] += 1
        if verdict == "coined":
            coined.append(phrase); continue
        quotes = [next(g for g in q if g) for q in _QUOTE.findall(prov)]
        bare = _QUOTE.sub(" ", prov)
        toks = re.findall(r"[A-Za-z][\w:.\-]*[\w]", bare)
        keys = [t for t in toks if t in bib or (not bib and _AUTHOR_YEAR.match(t))]
        keys += re.findall(r"<citekey>|\\cite[a-z]*\{[^}]+\}", bare)
        if bib:
            ghost = [t for t in toks if _AUTHOR_YEAR.match(t) and t not in bib]
            if ghost:
                print(f"  {where}: key(s) not in the .bib: {', '.join(ghost[:4])}"); warn += 1
        if verdict == "plain":
            if kind == "concept":
                print(f"  {where}: 'plain' concept without a source: cite the field paper that uses it "
                      "(borrowed) or move it to a '% term:' line"); warn += 1
            continue
        if not keys:
            print(f"  {where}: {verdict} without a citation key from the cited literature"); warn += 1
        if verdict == "borrowed" and not quotes:
            print(f"  {where}: borrowed without a quoted source (add \"<= 15 words\" from the cited paper, same sense)"); warn += 1
        for q in quotes:
            if not q.startswith("<") and len(q.split()) > 15:
                print(f"  {where}: source quote has {len(q.split())} words (keep <= 15)"); warn += 1
    n_c = sum(1 for r in rows if r[0] == "concept")
    print(f"  term table: {n_c} concept + {len(rows) - n_c} term rows; "
          + ", ".join(f"{v} {tally[v]}" for v in TERM_VERDICTS) + f" (coined max {TERM_COINED_MAX})")
    if not rows:
        print("  -- no rows: build the term table before drafting (concept table + '% term:' lines)")
    if len(coined) > TERM_COINED_MAX:
        print(f"  TOO MANY coined terms ({len(coined)}): {', '.join(coined)}; borrow the cited papers' "
              "terms or use plain words"); warn += 1
    # every "(termed X)" in the live text needs a table row
    declared = {_norm(r[1]) for r in rows}
    files = [p for p in chapters + [main_path] if os.path.basename(p) not in LINT_SKIP]
    shown: dict[str, int] = {}
    seen_files = set()
    for p in files:
        if p in seen_files:
            continue
        seen_files.add(p)
        raw = read(p)
        if p == main_path:
            head, sep, tail = raw.partition("\\begin{document}")
            raw = "\n" * head.count("\n") + sep + tail if sep else raw
        body = _KEYARG.sub(lambda m: " " * len(m.group(0)), uncomment(raw))
        rel = os.path.relpath(p, paper_dir)
        for m in re.finditer(r"\(termed\s+((?:[^()]|\([^()]*\))+)\)", body):
            ph = re.sub(r"\\concept" + _ARG, lambda k: k.group(1), m.group(1))
            ph = re.sub(r"^\s*(?:a|an|the)\s+", "", re.split(r"[;,]|\\eg\b|\\ie\b", ph)[0])
            if declared and _norm(ph) not in declared:
                print(f"  {rel}:{body.count(chr(10), 0, m.start()) + 1}: '(termed {ph.strip()[:40]})' has no "
                      "concept/term row with its source"); warn += 1
        for pat, hint, ok in SENSE_CLASH:
            for m in re.finditer(pat, body, flags=re.I):
                ls, le = body.rfind("\n", 0, m.start()) + 1, body.find("\n", m.end())
                ctx = body[max(ls, m.start() - 60):(le if le >= 0 else len(body))][:140]
                if ok and re.search(ok, ctx, flags=re.I):
                    continue
                shown[hint] = shown.get(hint, 0) + 1
                warn += 1
                if shown[hint] <= cap:
                    print(f"  {rel}:{body.count(chr(10), 0, m.start()) + 1}: sense clash '{m.group(0)}': {hint}")
    for hint, c in shown.items():
        if c > cap:
            print(f"  ... {c - cap} more of: {hint[:60]} (--habits-max N to show more)")
    return warn


# ----------------------------------------------------------------------------- vocabulary
# prose.md "Plain words, no coinage": hyphenated compounds <= 41 per 1,000 main-text words (source
# papers: about 14-41 per 1,000 words, median about 27); low-frequency words should be plain. The
# rare-word list is printed only when a reference vocabulary is passed with --vocab PATH: one lower-case
# word per line, "#" comments allowed, e.g. built from the main text of your own published papers
# (prose.md explains how). No word list ships with the skill.


def vocab_checks(main_path: str | None, paper_dir: str, vocab_path: str | None = None) -> int:
    if not main_path:
        return 0
    chapters = [f for f in live_chapters(read(main_path), paper_dir)
                if chapter_key(f) in KEYS and not re.search(r"appendix", os.path.basename(f), re.I)]
    text = " ".join(strip_tex(read(f)) for f in chapters)
    toks = re.findall(r"[A-Za-z][A-Za-z'\-]*[A-Za-z]|[A-Za-z]", text)
    if not toks:
        return 0
    hy = {}
    for t in toks:
        if "-" in t:
            hy[t.lower()] = hy.get(t.lower(), 0) + 1
    rate = 1000 * sum(hy.values()) / len(toks)
    hits = 0
    print(f"  hyphenated compounds: {rate:.1f} per 1,000 words (source papers: about 14-41, median about 27; max 41)")
    if rate > 41:
        print("  TOO MANY compounds: replace one-off coinages with plain phrases"); hits += 1
    low = sorted(w for w, c in hy.items() if c <= 2)
    if low:
        print("  one-off compounds (check each is a standard term, else rephrase): " + ", ".join(low[:60]))
    declared = set()
    for f in live_files(main_path, paper_dir):
        for m in re.finditer(r"^\s*%\s*concept:\s*([^|\n]+)\|", read(f), flags=re.M):
            declared.update(m.group(1).lower().split())
    if not vocab_path:
        print("  rare-word list skipped (no --vocab file)")
    elif not os.path.exists(vocab_path):
        print(f"  rare-word list skipped: --vocab file not found: {vocab_path}")
    else:
        vocab = {w.strip().lower() for w in open(vocab_path, encoding="utf-8")
                 if w.strip() and not w.lstrip().startswith("#")}
        counts: dict[str, int] = {}
        for t in toks:
            if "-" in t or len(t) < 8 or not t.islower():
                continue                          # long, lower-case words only: short ones are almost always plain
            counts[t] = counts.get(t, 0) + 1
        rare = sorted(w for w, c in counts.items() if c <= 2 and w not in vocab and w not in declared)
        if rare:
            print(f"  long low-frequency words outside the reference vocabulary ({len(rare)}; keep field terms, rephrase obscure ones):")
            print("    " + ", ".join(rare[:80]))
    return hits


# ----------------------------------------------------------------------------- cohesion (soft targets)
# prose.md section 4b: in the source papers about 47% of sentences are connective-led (Intro ~62%, Method
# ~48%, Experiments ~36%, hand-labelled), 1.8-2.5 connective sentences per 100 words; ~25% of connective
# sentences also carry this/these/such; ", so" + clause is absent from their main text.
CONNECTIVE_START = re.compile(
    r"^(?:However|In contrast|While|Although|Though|Despite|Whereas|Yet|Nevertheless|Nonetheless|Conversely|"
    r"Instead|Unlike|Compared|Moreover|Additionally|Furthermore|In addition|Besides|Specifically|Here|That is|"
    r"In other words|Formally|More formally|In practice|Concretely|In particular|For example|For instance|"
    r"Consider|Considering|Taking|As a result|Therefore|Thus|Hence|Consequently|Accordingly|As such|Since|"
    r"Because|As|When|Unless|To|Towards|Based on|Motivated by|Inspired by|Guided by|Grounded in|Building on|"
    r"Benefiting from|Having|First|Firstly|Second|Secondly|Third|Then|After that|Next|Finally|Lastly|"
    r"On the one hand|On one hand|On the other hand|If|Overall|Together|Generally|In summary|In short|"
    r"We highlight|In this section|Meanwhile|Similarly|Notably|Clearly|Obviously|Otherwise|Beyond|Apart from)\b")
MID_CONNECTIVE = re.compile(r"^\S+(?:\s+\S+)?\s+(?:further|also|thereby|then|therefore|thus)\b", re.I)
ANAPHOR_START = re.compile(r"^(?:This|These|Such|That|Those|It|Its|They|Their|Both)\b")
COHESION_TARGET = {"introduction": 55, "methodology": 45, "experiments": 35}   # min connective-led %
_STOP = set("about above after again their there these those which while where whose would could should "
            "being other under between through during before within without every each from with that this "
            "into over such than then them they what when also only very more most much many some".split())


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text)
    return [s.strip(" ()\"'`") for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text) if len(s.split()) >= 4]


def _content(s: str) -> set[str]:
    return {w.lower()[:5] for w in re.findall(r"[A-Za-z][A-Za-z\-]{4,}", s) if w.lower() not in _STOP}


def main_text_chapters(main_path: str, paper_dir: str) -> list[str]:
    """Chapter files \\input before \\appendix in the main file (the main text proper)."""
    src = uncomment(read(main_path))
    cut = src.find("\\appendix")
    out = []
    for f in live_chapters(src[:cut] if cut >= 0 else src, paper_dir):
        if re.search(r"appendix", os.path.basename(f), re.I) or "\\appendix" in uncomment(read(f)):
            break                                     # \appendix issued inside a chapter file
        if chapter_key(f) in KEYS:
            out.append(f)
    return out


def cohesion_checks(main_path: str | None, paper_dir: str) -> None:
    if not main_path:
        return
    chapters = main_text_chapters(main_path, paper_dir)
    tot_s = tot_c = tot_w = 0
    print("  " + "chapter".ljust(28) + "sent  conn-led  conn/100w  dbl-lock  anaph-led  ~isolated")
    for f in chapters:
        ck = chapter_key(f)
        txt = strip_tex(read(f)).replace(" MATH ", " X ")
        sents = _sentences(txt)
        if len(sents) < 3:
            continue
        nw = words(txt)
        c = dl = an = iso = 0
        prev = None
        for s in sents:
            is_c = bool(CONNECTIVE_START.match(s) or MID_CONNECTIVE.match(s))
            is_a = bool(ANAPHOR_START.match(s))
            if is_c:
                c += 1
                if re.search(r"\b(?:this|these|such)\b", " ".join(s.split()[:8]), re.I):
                    dl += 1
            if is_a:
                an += 1
            if prev is not None and not is_c and not is_a and not (_content(s) & _content(prev)):
                iso += 1
            prev = s
        n = len(sents)
        tot_s += n; tot_c += c; tot_w += nw
        share = 100 * c / n
        tgt = COHESION_TARGET.get(ck)
        flag = f"  below {tgt}%" if tgt and share < tgt else ""
        print(f"  {os.path.basename(f)[:27]:28s}{n:4d}  {share:6.1f}%  {100 * c / max(1, nw):8.2f}  "
              f"{100 * dl / max(1, c):7.1f}%  {100 * an / n:8.1f}%  {100 * iso / max(1, n - 1):8.1f}%{flag}")
    if tot_s:
        share = 100 * tot_c / tot_s
        print(f"  {'main text':28s}{tot_s:4d}  {share:6.1f}%  {100 * tot_c / max(1, tot_w):8.2f}"
              f"   targets: conn-led 45-55% (Intro >= 55, Method >= 45, Exp >= 35); ~2.2 per 100 words;"
              f" dbl-lock ~25% of connective sentences; isolated <= 5% (Intro/Method <= 3%)")
        print("  (~isolated = no connective, anaphor or shared content word with the previous sentence: a rough"
              " proxy; label C/A/L/S/N by hand for the real rate, prose.md section 4b)")
        print("  (this proxy on the source papers: conn-led about 40-52%, Intro 58-70%, Exp 32-42%;"
              " ~isolated Intro 3-4%, Exp 13-24%: read the targets with that offset)")
    body = " ".join(uncomment(read(f)) for f in chapters)
    so = len(re.findall(r",\s+so\s+(?!that\b|as\b|far\b|on\b|forth\b|much\b|many\b|called\b|-called)[A-Za-z\\$]", body))
    rate = 1000 * so / max(1, tot_w)
    print(f"  ', so' + clause: {so} ({rate:.1f} per 1k words; cap 1.0; absent from the source papers' main text)"
          + ("  OVER CAP: split, open with 'Therefore,' / 'As a result,' or front 'Since ...,'" if rate > 1.0 else ""))
    core = 0
    for f in live_files(main_path, paper_dir):
        core += len(re.findall(r"^\s*%\s*concept:\s*[^|\n]+\|\s*core\s*\|", read(f), flags=re.M))
    termed = len(re.findall(r"\(\s*termed\b", body))
    print(f"  '(termed X)': {termed} in the main text; core concepts declared: {core} (termed <= core; source papers 1-3)"
          + ("  TOO MANY: keep '(termed X)' for the core concepts, use '(\\ie ...)' or a plain phrase" if termed > max(core, 3) else ""))


# ----------------------------------------------------------------------------- habits (warnings)
# prose.md "Habits to avoid": 27 recurring patterns of machine-written drafts + foreign connectives;
# (id, pattern, flags, plain alternative). Some patterns also catch legitimate uses: read the line first.
HABITS = [
    ("1 ', so' + clause", r",\s+so\s+(?!that\b|as\b|far\b|on\b|forth\b|much\b|many\b|called\b|-called)[A-Za-z\\$]", 0,
     "split; 'Therefore,' / 'As a result,' / fronted 'Since ...,' / ', thereby V-ing'"),
    ("2 'every'", r"\bevery\b", re.I, "'each' / 'for each' (the source papers' default)"),
    ("3 motion verb", r"\b(?:shrinks?|shrinking|grows|beats?|caps|stays|lies within|falls (?:from|to)|lowers|raises)\b", 0,
     "reduces / decreases / increases / remains / outperforms / is within"),
    ("4 'against' = compared with", r"\bAgainst\b|\bagainst\b(?!\s+(?:\S+\s+)?(?:noise|perturbations?|corruptions?|outliers?|threats?|shifts?))", 0,
     "compared to / compared with / 'with X as ground truth' / 'correlation between X and Y'"),
    ("5 coined label", r"\b(?:headline|seed[- ]means?|sweep(?:s|ing)?|by construction|catalogue|arms?|surrogate|analogue|noise floor|stress[- ]tests?)\b", re.I,
     "main result / the average over seeds / baselines / a plain description"),
    ("6 draft-wide label", r"\b(?:ideali[sz](?:ed|ation|e)|regimes?|resolv(?:e|es|ed|able)|additiv(?:e|ity))\b", re.I,
     "simplified / setting / detect, distinguish; decide once, change every file"),
    ("7 proof register", r"\b(?:recovers?|reduces? to|amounts? to|coincides?|speciali[sz](?:ing|ation)|in place of|iterates|inductively|whenever|rests? on)\b", re.I,
     "is equivalent to / corresponds to / replacing X with Y / relies on / when / yields"),
    ("8 bare appendix pointer", r"\(\s*Appendix\s*~?\s*\\ref", 0, "'(see Appendix~\\ref{})' / '... can be found in Appendix~\\ref{}'"),
    ("9 'needs' / 'extra'", r"\bneeds\b|\bextra\b", re.I, "requires / additional / without additional"),
    ("10 derivation 'gives'", r"\b(?:which gives|gives|giving)\b", 0, "'yields:' for a derivation step ('Figure X gives examples' is fine)"),
    ("11 metaphor verb", r"\b(?:pays?|buys?|one-time cost|trades?\b[^.]{0,40}\bagainst|carr(?:y|ies))\b", re.I,
     "requires / reduces / share the same / contains / improves / affects"),
    ("12 prediction wording", r"\bis (?:expected|predicted) to\b|\b(?:makes|gives|carries) no prediction", re.I,
     "should / may / is likely to / 'the analysis does not predict'; 'is expected to' only in bold predictions, <= 2 per section"),
    ("13 mid-sentence 'therefore'", r"(?<=[a-z,])\s+therefore\b", 0, "sentence-initial 'Therefore,'"),
    ("14 sentence-initial 'Its'", r"(?:^|[.!?]\s+)Its\s", re.M, "name the referent (prose.md section 4b rule 7)"),
    ("15 stance predicate", r"\bis (?:standard|established)\b|\bstandard practice\b|\bwe claim\b|\bnot a (?:claimed )?contribution\b", re.I,
     "'is widely adopted' / '..., rather than a contribution of this paper'"),
    ("16 table as agent", r"(?:Table|Figure)~?\s*\\ref\{[^}]*\}\s+(?:lists|compares|measures|gives|scores|recomputes)\b", 0,
     "'We report ... in Table X' / 'Table X reports / summarizes / shows'"),
    ("17 'the theory' as subject", r"\b[Tt]he theory (?:checks?|predicts?|does|shows|says)\b|What the theory predicts", 0,
     "'our analysis ...' / 'we do not predict ...'"),
    ("18 scope limit", r"\bdoes not cover\b|\blies outside\b|\bcovers only\b", re.I, "beyond / 'is (still) limited to'"),
    ("19 question-style run-in", r"\\textbf\{(?:What|Why|How|When|Which|Where)\b[^}]{0,60}\.\}", 0, "noun-phrase heads: 'Impact of X.'"),
    ("20 'we write' notation", r"\b[Ww]e write\b", 0, "'..., where X denotes ...' / 'denoted as'"),
    ("21 'X, not Y' tail", r",\s+not\s+(?:a|an|the|on|in|by|for|to)\b", 0, "'rather than'"),
    ("22 'is called' rule", r"\b(?:is|are) called\b|\bcalls? a tie\b|\btie called\b", 0, "'is considered X if ...'"),
    ("23 mid-sentence ', however'", r",\s*however\b", 0, "sentence-initial 'However,'"),
    ("24 'the latter/former'", r"\b[Tt]he (?:latter|former)\b", 0, "repeat the noun"),
    ("25 'next to'", r"\bnext to\b", re.I, "'together with'"),
    ("26 'flag(ged)'", r"\bflag(?:s|ged|ging)?\b", re.I, "'mark(ed)'"),
    ("27 'into context'", r"\b(?:put|puts|placed?) [^.]{0,40}\binto context\b|\bin context\b", re.I, "'serves as a reference for'"),
    ("+ foreign connective", r"\bIdeally,|(?:^|[.!?]\s+)Nor\s|\blikewise\b|\bis not free\b|\bempirical question\b|\bAs a direct corollary\b", re.M,
     "'Intuitively, effective X should' / 'It also does not' / 'Moreover,' / 'requires additional' / 'we test whether' / 'Based on Proposition~\\ref{}'"),
]


def habit_checks(files: list[str], paper_dir: str, main_path: str | None, cap: int) -> int:
    total = 0
    found: dict[str, list[str]] = {}
    for p in files:
        raw = read(p)
        if p == main_path:
            head, sep, tail = raw.partition("\\begin{document}")
            raw = "\n" * head.count("\n") + sep + tail if sep else raw
        body = uncomment(raw)
        for hid, pat, flags, _ in HABITS:
            seen = set()
            for m in re.finditer(pat, body, flags=flags):
                line = body.count("\n", 0, m.start()) + 1
                if line in seen:
                    continue
                seen.add(line)
                ctx = body[max(0, m.start() - 30):m.end() + 30].replace("\n", " ")
                found.setdefault(hid, []).append(f"{os.path.relpath(p, paper_dir)}:{line}: ...{ctx.strip()}...")
    alt = {h[0]: h[3] for h in HABITS}
    for hid, _, _, _ in HABITS:
        hits = found.get(hid, [])
        if not hits:
            continue
        total += len(hits)
        print(f"  [{hid}] {len(hits)} line(s) -> use: {alt[hid]}")
        for h in hits[:cap]:
            print(f"    {h}")
        if len(hits) > cap:
            print(f"    ... {len(hits) - cap} more (--habits-max N to show more)")
    # 'every' rate against 'each' (source papers: about 0.1 vs 1.8 per 1k words)
    txt = " ".join(strip_tex(read(p)) for p in files)
    nw = max(1, words(txt))
    ev, ea = len(re.findall(r"\bevery\b", txt, re.I)), len(re.findall(r"\beach\b", txt, re.I))
    print(f"  'every' {1000 * ev / nw:.2f} per 1k words vs 'each' {1000 * ea / nw:.2f} (source papers: about 0.1 vs 1.8)")
    return total


# ----------------------------------------------------------------------------- intro & contributions
# references/introduction.md (IR1-IR15) and references/contributions.md (KR1-KR14): the greppable parts.
# The house finals: 0 contribution lists, 0 "novel" / self-referential "first" / "To the best of our knowledge"
# in abstract, intro and conclusion, 0 "Different from them" / "Our work differs from them" (reference-lineage forms),
# 0 sentence-initial "Ideally,"; one epithet repeated verbatim in abstract, intro, Methodology opener and
# Conclusion (declare it with a "% epithet: <phrase>" line, like "% concept:"). Not greppable (read for it):
# root-cause sentence, standard before weaknesses, key idea = negation, self-deprecation ("this mapping is simple").
CONTRIB_LIST = re.compile(r"(?:our|the) (?:main |key )?contributions? (?:are|is|can be summari[sz]ed|as follows)|"
                          r"summari[sz]e (?:our|the) (?:main |key )?contributions|we make the following contributions|"
                          r"contributions of this (?:paper|work) (?:are|is)", re.I)
NOVEL_FIRST = re.compile(r"\bnovel(?:ly)?\b|\b(?:we are|is|are|was|were) the first\b|\bfor the first time\b|"
                         r"\bthe first (?:work|study|paper|method|attempt|approach|framework|investigation|model|to)\b|"
                         r"\bfirst-ever\b", re.I)
EVERYWHERE = [
    (r"(?i)to the best of our knowledge|as far as we know", "KR1: 'To the best of our knowledge' (0 in the house finals): let the contrast show the novelty"),
    (r"(?i)\bdifferent from (?:them|these|those|existing|prior|previous|all)\b|\bour (?:work|method|approach|study|paper) (?:differs?|is different) from\b|\bdiffers? from (?:them|these|those) in\b",
     "IR12/KR14: reference-style difference sentence (house 0): end the RW paragraph on the drawback label or 'remains largely underexplored'"),
    (r"(?i)\b(?:is|are) not (?:our|a) (?:main |claimed )?contributions?\b|\bnot our contribution\b",
     "KR14: 'is not our contribution': credit the borrowed part in the same sentence ('following X', 'widely adopted') instead"),
    (r"(?:^|[.!?]\s+)Ideally,", "IR14: sentence-initial 'Ideally,' (house 0): 'Intuitively, effective X should be A (\\ie ...) and B (\\ie ...)', set before the first 'However'"),
]
RESERVATION_END = re.compile(r"\bhowever\b|\bunclear\b|\bany (?:benefit|advantage)\b|\bremains? (?:an )?open\b", re.I)
PROPOSAL = re.compile(r"\bwe (?:propose|introduce|present)\b", re.I)
STRONG_RESULT = re.compile(r"\b(?:demonstrat(?:e|es|ed|ing)|validat(?:e|es|ed|ing)|verif(?:y|ies|ied|ying)|"
                           r"prov(?:e|es|ed|en|ing)|consistently|significantly)\b", re.I)


def _blank_outside(raw: str, start: int, end: int) -> str:
    """Keep raw[start:end], replace everything else by its newlines (line numbers stay valid)."""
    return "\n" * raw.count("\n", 0, start) + raw[start:end] + "\n" * raw.count("\n", end)


def _drop_comment_lines(raw: str) -> str:
    """Remove comment-only lines, so that they do not split a paragraph (used for paragraph splitting only)."""
    return "\n".join(l for l in raw.split("\n") if not re.match(r"^\s*%", l))


def _zones(main_path: str, paper_dir: str) -> dict[str, list[tuple[str, str]]]:
    """abstract / introduction / methodology (opener) / conclusion -> [(file, uncommented text with the
    original line numbers)]. Chapter files first; the abstract may also live in the main file."""
    z: dict[str, list[tuple[str, str]]] = {k: [] for k in ("abstract", "introduction", "methodology", "conclusion")}
    for f in main_text_chapters(main_path, paper_dir) + [f for f in live_chapters(read(main_path), paper_dir)
                                                          if chapter_key(f) == "abstract"]:
        k = chapter_key(f)
        if k not in z or any(f == g for g, _ in z[k]):
            continue
        body = uncomment(read(f))
        if k == "methodology":                       # opener = text before the first \subsection
            m = re.search(r"\\subsection\*?\{", body)
            body = _blank_outside(body, 0, m.start()) if m else body
        if k == "conclusion":                        # the file also holds Limitations: keep the Conclusion
            m = re.search(r"\\section\*?\{Conclusions?\}", body)
            if m:
                body = _blank_outside(body, m.start(), len(body))
        z[k].append((f, body))
    if not z["abstract"]:
        body = uncomment(read(main_path))
        m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", body, flags=re.S)
        if m:
            z["abstract"].append((main_path, _blank_outside(body, m.start(1), m.end(1))))
    return z


def _pending_results(files: list[str]) -> tuple[int, int]:
    """(\\pend cells, '--' cells in tables without any decimal number) over every live file."""
    pend = dash = 0
    for f in files:
        for tab in re.findall(r"\\begin\{tabular\*?\}(.*?)\\end\{tabular\*?\}", uncomment(read(f)), flags=re.S):
            pend += len(re.findall(r"\\pend\b", tab))
            cells = [c.strip() for row in re.split(r"\\\\", tab) for c in row.split("&")]
            d = sum(1 for c in cells if c in ("--", "$--$", "-"))
            if d >= 3 and not re.search(r"\d+\.\d+", tab):
                dash += d
    return pend, dash


def intro_contrib_checks(main_path: str | None, paper_dir: str, cap: int) -> int:
    if not main_path:
        return 0
    warn = 0
    zones = _zones(main_path, paper_dir)
    files = [f for f in live_files(main_path, paper_dir) if os.path.basename(f) not in LINT_SKIP]

    def show(rel: str, body: str, pos: int, why: str, shown: dict) -> None:
        nonlocal warn
        warn += 1
        shown[why] = shown.get(why, 0) + 1
        if shown[why] <= cap:
            ctx = body[max(0, pos - 30):pos + 50].replace("\n", " ").strip()
            print(f"  {rel}:{body.count(chr(10), 0, pos) + 1}: {why}: ...{ctx}...")

    shown: dict[str, int] = {}
    # KR1 / D1: contribution list; "novel" / "first" in abstract, intro, conclusion (the whole chapter file)
    for k in ("abstract", "introduction", "conclusion"):
        for f, _ in zones[k]:
            body = uncomment(read(f)) if f != main_path else zones[k][0][1]
            rel = os.path.relpath(f, paper_dir)
            for m in NOVEL_FIRST.finditer(body):
                show(rel, body, m.start(), f"KR1: '{m.group(0)}' in the {k} (0 in the house finals; novelty by contrast, D7)", shown)
            if k == "introduction":
                for m in CONTRIB_LIST.finditer(body):
                    show(rel, body, m.start(), "D1/IR14: contribution-list phrasing (no house final has one): end with the First/Second/Third evidence roadmap", shown)
                for m in re.finditer(r"\bwe argue\b", body, re.I):
                    show(rel, body, m.start(), "IR14: 'we argue' in the Introduction (reference-lineage form; house 0)", shown)
    # everywhere (main text + appendix Related Works)
    for f in files:
        raw = read(f)
        if f == main_path:
            head, sep, tail = raw.partition("\\begin{document}")
            raw = "\n" * head.count("\n") + sep + tail if sep else raw
        body = uncomment(raw)
        for pat, why in EVERYWHERE:
            for m in re.finditer(pat, body, flags=re.M):
                show(os.path.relpath(f, paper_dir), body, m.start(), why, shown)
    # KR10 / IR8: abstract and intro paragraphs that end on a reservation, from the proposal sentence on
    # (a gap sentence such as "However, ... remains largely unexplored" before the proposal is the style)
    for k in ("abstract", "introduction"):
        for f, body in zones[k]:
            text = body if f == main_path else uncomment(_drop_comment_lines(read(f)))
            proposed = False
            for para in re.split(r"\n\s*\n", text):
                sents = _sentences(strip_tex(para).replace(" MATH ", " X "))
                proposed = proposed or bool(PROPOSAL.search(" ".join(sents)))
                if proposed and sents and RESERVATION_END.search(sents[-1]):
                    warn += 1
                    print(f"  {os.path.relpath(f, paper_dir)}: KR10: {'an' if k[0] in 'aeiou' else 'a'} {k} paragraph ends on a reservation: ...{sents[-1][-90:]}"
                          "  -> make it an RQ premise ('Since ..., we investigate whether ...')")
    # KR2: the declared epithet in the four places
    epithets = []
    for f in live_files(main_path, paper_dir):
        epithets += [m.group(1).strip() for m in re.finditer(r"^\s*%\s*epithet:\s*(.+?)\s*$", read(f), flags=re.M)]
    if not epithets:
        print("  info: no '% epithet: <phrase>' line in the main file: declare the method epithet to count it "
              "in abstract / intro / Methodology opener / Conclusion (contributions.md KR2)")
    for ep in epithets:
        if ep.startswith("<"):
            print("  info: the '% epithet:' line is still the template placeholder: fill in the method epithet (KR2)")
            continue
        pat = re.compile(r"\b" + r"[\s~-]+".join(re.escape(w) for w in re.split(r"[\s-]+", ep) if w) + r"\b", re.I)
        row = {}
        for k in ("abstract", "introduction", "methodology", "conclusion"):
            row[k] = sum(len(pat.findall(strip_tex(body))) for _, body in zones[k]) if zones[k] else None
        cells = "  ".join(f"{k[:5]} {'-' if v is None else v}" for k, v in row.items())
        print(f"  epithet '{ep}': {cells}   (house papers: verbatim in all four, 4-5x)")
        for k, v in row.items():
            if v == 0:
                warn += 1
                print(f"    MISSING in the {k if k != 'methodology' else 'Methodology opener'}: repeat the epithet word for word (KR2)")
    # KR7: strong result verbs while results are pending
    pend, dash = _pending_results(files)
    if pend or dash:
        print(f"  pending results: {pend} \\pend cell(s), {dash} '--' cell(s) in number-free tables -> "
              "stop at the design tier (investigate whether / is expected to; contributions.md C.7, KR7)")
        for f in main_text_chapters(main_path, paper_dir):
            body = uncomment(read(f))
            body = re.sub(r"\\begin\{(tabular\*?)\}.*?\\end\{\1\}", lambda m: "\n" * m.group(0).count("\n"), body, flags=re.S)
            for m in STRONG_RESULT.finditer(body):
                show(os.path.relpath(f, paper_dir), body, m.start(),
                     f"KR7: '{m.group(0)}' with results pending (fine for a proof or a cited result; not for own results)", shown)
    for why, c in shown.items():
        if c > cap:
            print(f"  ... {c - cap} more of: {why[:60]} (--habits-max N to show more)")
    return warn


# ----------------------------------------------------------------------------- sentences (warnings)
# prose.md section 12: sentence structure, subject consistency and emphasis. Thresholds are the range of
# the five current source papers (hand-annotated samples plus corpus counts). Word
# counts: inline math = 1 word, citations not counted. Exact: length, parentheticals, Since openers,
# This/These openers, pointer endings. Approximate (read the line): long front, two main clauses,
# mid-sentence 'which', contrast direction, key claim in a subordinate slot, fragments.
SENT_MEAN = {"abstract": 26, "introduction": 26, "preliminary": 27, "methodology": 27, "experiments": 21, "conclusion": 26}
SENT_OVER35 = {"abstract": 33, "introduction": 19, "preliminary": 25, "methodology": 25, "experiments": 9, "conclusion": 33}
SENT_PAREN = {"abstract": 0.45, "introduction": 0.5, "preliminary": 0.35, "methodology": 0.35, "experiments": 0.39, "conclusion": 0.45}
_ABBR = [(r"\\ie\b\.?", "ie"), (r"\\eg\b\.?", "eg"), (r"\\cf\b\.?", "cf"), (r"\\etal\b\.?", "et al"),
         (r"\bi\.e\.", "ie"), (r"\be\.g\.", "eg"), (r"\bcf\.", "cf"), (r"\bet al\.", "et al"),
         (r"\b(App|Sec|Fig|Eq|Prop|Thm|Tab|resp|vs)\.", r"\1")]
_OPENER = r"^(?:(?:First|Second|Third|Finally|Therefore|Thus|Moreover|Furthermore|However|Specifically|Hence|In addition),\s+)?"
_SUBJ = r"(?:we|it|they|this|these|such|the|a|an|each|our|its|their|both|[A-Z][A-Za-z\-]+)"


def _sent_clean(line: str) -> str:
    s = re.sub(r"(?<!\\)%.*", "", line)
    for a, b in _ABBR:
        s = re.sub(a, b, s)
    s = re.sub(r"\$[^$]*\$", " X ", s)
    s = re.sub(r"~?\\cite[pt]?\*?(\[[^\]]*\])?\{[^}]*\}", " \u2020", s)
    s = re.sub(r"\\(?:ref|eqref|Eqref|autoref|cref)\{[^}]*\}", "1", s)
    s = re.sub(r"\\(?:label|footnote)\{[^}]*\}", "", s)
    s = re.sub(r"\\item\b", "\n\n", s)
    for _ in range(2):
        s = re.sub(r"\\(?:textbf|textit|emph|concept|draft|underline|text)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\(?:begin|end)\{[^}]*\}(\[[^\]]*\])?", " ", s)
    s = re.sub(r"\\[A-Za-z@]+\*?", " ", s)
    return re.sub(r"[{}~]", " ", s)


def _sent_units(path: str) -> list[tuple[int, str, int]]:
    """(line, sentence, paragraph id) for the prose of one chapter file."""
    raw = read(path).split("\n")
    skip_env = re.compile(r"\\begin\{(figure\*?|table\*?|algorithm|equation\*?|align\*?|gather\*?|tabular\*?|wrapfigure|tcolorbox)\}")
    out, buf, para, depth_env = [], [], 0, None
    def flush():
        nonlocal buf, para
        if not buf:
            return
        text = ""; starts = []
        for ln, t in buf:
            starts.append((len(text), ln)); text += t + " "
        pos = 0
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])", text):
            st = text.find(s, pos); pos = st + len(s)
            ln = max(l for o, l in starts if o <= max(st, 0)) if starts else 0
            if len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", s)) >= 4:
                out.append((ln, s.strip(), para))
        buf = []; para += 1
    for i, line in enumerate(raw, 1):
        if depth_env:
            if re.search(r"\\end\{%s\}" % re.escape(depth_env), line):
                depth_env = None
            continue
        m = skip_env.search(line)
        if m and not line.lstrip().startswith("%"):
            flush(); depth_env = m.group(1)
            if re.search(r"\\end\{%s\}" % re.escape(depth_env), line[m.end():]):
                depth_env = None
            continue
        if line.lstrip().startswith("%"):
            continue
        if re.match(r"\s*\\(?:section|subsection|subsubsection|paragraph)\*?\{", line):
            flush(); continue
        c = _sent_clean(line)
        for k, piece in enumerate(c.split("\n\n")):
            if k:
                flush()
            if piece.strip():
                buf.append((i, piece.strip()))
        if not c.strip():
            flush()
    flush()
    return out


def _parens(s: str) -> list[str]:
    out = []
    for m in re.finditer(r"\(([^()]*)\)", s):
        inner = m.group(1).strip()
        if not inner or re.fullmatch(r"(?:X|\d+|[ivx]+|[a-z]|see \w+ \d+|\w+ \d+|cf \w+ \d+)", inner, re.I):
            continue
        if len(inner.split()) < 2:
            continue
        out.append(inner)
    return out


def sentence_checks(main_path: str | None, paper_dir: str, cap: int) -> int:
    if not main_path:
        return 0
    chapters = main_text_chapters(main_path, paper_dir)
    abs_file = [f for f in live_chapters(uncomment(read(main_path)), paper_dir) if chapter_key(f) == "abstract"]
    chapters = [f for f in abs_file if f not in chapters] + chapters
    src_all = " ".join(read(f) for f in chapters)
    mname = re.search(r"\\textbf\{([A-Z][A-Za-z0-9\-]+)\}", " ".join(uncomment(read(f)) for f in abs_file) or src_all)
    method = mname.group(1) if mname else None
    warn = 0
    lists: dict[str, list[str]] = {}
    def note(key: str, f: str, ln: int, s: str, extra: str = ""):
        lists.setdefault(key, []).append(f"    {os.path.relpath(f, paper_dir)}:{ln}: {extra}{s[:90]}{'...' if len(s) > 90 else ''}")
    print("  " + "chapter".ljust(26) + "sent  mean  med  >35   >45  paren/s  2-clause  Since  This-led  ptr-end")
    for f in chapters:
        ck = chapter_key(f) or ""
        units = _sent_units(f)
        if len(units) < 3:
            continue
        lens = [len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", s)) for _, s, _ in units]
        n = len(units)
        srt = sorted(lens); med = srt[n // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
        mean = sum(lens) / n
        o35 = sum(x > 35 for x in lens); o45 = sum(x > 45 for x in lens)
        npar = two = since = anaph = ptr = 0
        for (ln, s, pid), w in zip(units, lens):
            ps = _parens(s); npar += len(ps)
            if len(ps) >= 2:
                note("SR7 two or more parentheticals in one sentence (sources: one; 1-7% of sentences)", f, ln, s)
            for p in ps:
                if len(p.split()) > 10:
                    note("SR13 long parenthetical (> 10 words): a key claim may be hiding in it", f, ln, "(" + p + ")", "")
            if w > 45:
                note("SR2 sentence over 45 words (sources: <= 1 per section)", f, ln, s, f"[{w}w] ")
            body = re.sub(_OPENER, "", s)
            if re.match(r"Since\b", body):
                since += 1
                note("SR5 'Since' opener (sources 0-0.6% of sentences): state the result as the main clause", f, ln, s)
                if re.search(r"\b(?:rank\w*|first order|equivalent|show\w*|reduc\w*|outperform\w*|match\w*|prov\w*)\b", body.split(",")[0] + " " + " ".join(body.split(",")[1:3])):
                    note("SR13 a result inside the 'Since' clause: make it the main clause", f, ln, s)
            if re.match(r"(?:This|These|Such)\b", s):
                anaph += 1
            # a bare pointer as the last constituent; a trailing "(see ...)" and roadmap sentences are fine
            if re.search(r"(?:\b(?:in|see) (?:Section|Appendix|Table|Figure)s?~? ?[\dA-Z.]+(?: and [\dA-Z.]+)?|as (?:Figure|Table) [\dA-Z.]+ (?:shows|depicts|illustrates))\W*$", s) \
               and not re.match(r"(?:We first|First,|After that|Then,|Next,|Finally,|In this section)", s):
                ptr += 1
            if re.search(r"\b(?:is|are) illustrated in (?:Figure|Table)\b|\bas (?:Figure|Table) \S+ (?:shows|depicts)\b", s):
                note("SR14 the sentence ends on a figure/table pointer: put the pointer in front ('As shown in Figure X, ...')", f, ln, s)
            tail = " ".join(s.split()[-14:])
            if sum(bool(re.search(p, tail)) for p in [r"\(termed", r"\(see|\b(?:Section|Appendix) \d", "\u2020"]) >= 2 or \
               (re.search(r"\(termed", tail) and re.search(r"\((?:see )?(?:Section|Appendix)", tail)):
                note("SR14 two or more tails at the sentence end (termed / citation / pointer)", f, ln, s)
            if re.search(r"[,;]\s*(?:and|but|while|whereas)\s+" + _SUBJ + r"\s+(?:[a-z]+\s+){0,3}?(?:is|are|was|were|has|have|can|may|should|will|does|do|[a-z]+s|[a-z]+ed)\b", s) or \
               re.search(r";\s*" + _SUBJ + r"\s", s):
                two += 1
                if ck in ("abstract", "introduction"):
                    note("SR6 two main clauses with two subjects (sources: 5-17% of sentences): split, or keep one subject with two verbs", f, ln, s)
            m = re.match(r"(?:To|Since|While|If|When|As|Under|By|Based on|Although|Because|Given|Through|After|Before)\b", body)
            if m:
                sub = re.search(r",\s+(?:" + _SUBJ + r"|merging|training)\b", body)
                front = len(body[:sub.start()].split()) if sub else len(body.split())
                if front > 10:
                    note("SR4 more than 10 words before the subject (sources 0.6-3.5% of sentences)", f, ln, s, f"[{front}w front] ")
            if re.search(r",\s*which\b[^.,;]{3,80},\s*(?:is|are|was|were|has|have|can|may|sets?|makes?|[a-z]+s)\b", s):
                note("SR8 mid-sentence ', which ...,' between subject and verb: move it to the end (sources: only for concede-then-overturn)", f, ln, s)
            mw = re.search(r",\s*which\b(.*)$", s)
            if mw and len(mw.group(1).split()) > 10:
                note("SR13 long sentence-final ', which ...' clause: if it holds the point, make it the main clause", f, ln, s)
            mc = re.search(r"\b(?:while|whereas)\b(.*)$", s)
            if mc and re.search(r"\b(?:we|our|ours)\b" + (r"|" + re.escape(method) if method else ""), mc.group(1)):
                note("SR12 our method sits in the while/whereas clause: put it in the main clause, the baseline in the 'while' clause", f, ln, s)
            if re.match(r"(?:While|Although|Since|If|When|Because|Whereas)\b", s) and "," not in s:
                note("SR15 fragment: a subordinate clause with no main clause", f, ln, s)
            if re.match(r"It is \w+(?: \w+)? that\b|What [^,]{3,40} is\b", s):
                note("SR15 cleft sentence (sources: 0-1 per paper): state it directly", f, ln, s)
        for (ln, s, pid), w, (ln2, s2, pid2), w2 in zip(units, lens, units[1:], lens[1:]):
            if w > 35 and pid2 == pid and w2 > 30:
                note("SR3 long sentence followed by another long one (sources: a long sentence is often followed by a short one)", f, ln2, s2, f"[{w}w -> {w2}w] ")
        flags = []
        if ck in SENT_MEAN and mean > SENT_MEAN[ck]:
            flags.append(f"mean>{SENT_MEAN[ck]}")
        if ck in SENT_OVER35 and 100 * o35 / n > SENT_OVER35[ck]:
            flags.append(f">35 over {SENT_OVER35[ck]}%")
        if o45 > 1:
            flags.append(">45 x%d" % o45)
        if ck in SENT_PAREN and npar / n > SENT_PAREN[ck]:
            flags.append(f"paren>{SENT_PAREN[ck]}")
        if 100 * two / n > 17:
            flags.append("2-clause>17%")
        if 100 * since / n > 2:
            flags.append("Since>2%")
        if ck in ("introduction", "experiments") and 100 * anaph / n < 5:
            flags.append("This-led<5%")
        if ck in ("methodology", "experiments") and 100 * ptr / n > 12:
            flags.append("ptr-end>12%")
        warn += len(flags)
        print(f"  {os.path.basename(f)[:25]:26s}{n:4d}  {mean:4.1f}  {med:4.1f}  {100 * o35 / n:3.0f}%  {o45:3d}  {npar / n:6.2f}  "
              f"{100 * two / n:6.0f}%  {since:4d}  {100 * anaph / n:6.1f}%  {100 * ptr / n:5.1f}%"
              + (f"  <- {', '.join(flags)}" if flags else ""))
    print("  source ranges: mean ~20-22 (Abs <= 26, Intro <= 26, Method <= 27, Exp <= 21); >35 words 5-16% (Intro <= 19%,"
          " Exp <= 9%); >45 words <= 1 per section; paren/s 0.12-0.37; two main clauses 5-17%; Since openers 0-0.6%;"
          " This/These/Such-led 5.7-11%; pointer endings 6-12%")
    for key in sorted(lists):
        rows = lists[key]
        warn += len(rows)
        print(f"  [{key}] {len(rows)}")
        for r in rows[:cap]:
            print(r)
        if len(rows) > cap:
            print(f"    ... {len(rows) - cap} more")
    print("  (SR4/6/8/12/13/15 are pattern matches: read each line; SR9 subject roles and SR10 subject switches are"
          " checked by hand, prose.md section 12)")
    return warn


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paper_dir")
    ap.add_argument("--venue", default=None, choices=sorted(BLUEPRINT),
                    help="default: detected from the style kit the main .tex loads")
    ap.add_argument("--stage", default="submission", choices=["submission", "camera"])
    ap.add_argument("--limit", type=int, default=None, help="page limit from the CURRENT call for papers")
    ap.add_argument("--aux", default=None)
    ap.add_argument("--habits-max", type=int, default=8, metavar="N",
                    help="lines shown per habit pattern in the == habits block (default 8)")
    ap.add_argument("--vocab", default=None, metavar="PATH",
                    help="optional reference word list (one word per line, '#' comments) for the rare-word "
                         "check; without it only the hyphenated-compound checks run")
    a = ap.parse_args()

    main_path, main_src, det_venue, kit_year, opts = find_main(a.paper_dir)
    venue = a.venue or det_venue or "iclr"
    if a.venue and det_venue and a.venue != det_venue:
        print(f"WARNING: --venue {a.venue} but the main .tex loads the {det_venue} kit")
    bp = dict(BLUEPRINT[venue])
    limit = a.limit or VENUES[venue]["limit"][a.stage]
    if a.stage == "camera":                       # extra words go to Experiments + Introduction
        extra = CAMERA_TOTAL[venue][1] - bp["total"][1]
        for k, share in CAMERA_EXTRA.items():
            bp[k] = (bp[k][0], int(bp[k][1] + share * extra))
        bp["total"] = CAMERA_TOTAL[venue]
    print(f"== venue {venue} ({VENUES[venue]['columns']} column(s)), stage {a.stage}, page limit {limit}"
          f" (last verified {VENUES[venue]['verified']}; re-check the current call for papers)")

    chapters = live_chapters(main_src, a.paper_dir) if main_src else []
    if not chapters:
        chapters = sorted(glob.glob(os.path.join(a.paper_dir, "chapters", "*.tex")))
    if not chapters and not main_src:
        print("no chapters/*.tex and no main .tex found"); return 2
    print(f"== prose words (target total {bp['total'][0]}-{bp['total'][1]})")
    if not chapters:
        print("  no chapters/*.tex: word budget skipped (split the paper into chapters/ files)")
    total = 0
    for p in chapters:
        k = chapter_key(p)
        if k is None:
            continue
        n = words(strip_tex(read(p)))
        total += n
        lo, hi = bp[k]
        flag = "ok" if lo <= n <= hi else ("LOW" if n < lo else "HIGH")
        pref = TARGET[venue].get(k)
        if flag == "ok" and pref and not pref[0] <= n <= pref[1]:
            flag = f"ok (outside preferred {pref[0]}-{pref[1]})"
        print(f"  {os.path.basename(p):32s} {n:5d}  range {lo}-{hi}  {flag}")
    lo, hi = bp["total"]
    print(f"  {'TOTAL main text':32s} {total:5d}  target {lo}-{hi}  "
          f"{'ok' if lo <= total <= hi else ('LOW' if total < lo else 'HIGH')}")

    aux = a.aux or next(iter(glob.glob(os.path.join(a.paper_dir, "*.aux"))), None)
    print("== page check")
    if aux and os.path.exists(aux):
        m = re.search(r"\\newlabel\{main-text-end\}\{\{[^}]*\}\{(\d+)\}", read(aux))
        if m:
            page = int(m.group(1))
            verdict = ("ok: fills the limit" if page == limit else
                       f"UNDER: main text ends on p{page}; restore material from the appendix" if page < limit else
                       f"OVER: main text ends on p{page}; move material to the appendix / tighten floats")
            print(f"  main-text-end on page {page} (limit {limit}): {verdict}")
            print("  (also check visually that the last main page is full, not half-empty)")
        else:
            print("  \\label{main-text-end} not found in the .aux; put it after the Conclusion paragraph")
    else:
        print("  no .aux; build with: tectonic -X compile --keep-intermediates main.tex")

    print("== venue")
    vhits = 0
    if main_src:
        doc = expand(main_src, a.paper_dir)
        vhits = venue_checks(venue, a.stage, kit_year, opts, main_src, doc, a.paper_dir)
    else:
        print("  no main .tex (\\documentclass + \\begin{document}) found")
    print(f"  {vhits} hit(s)")

    print("== concepts")
    chits = concept_checks(main_path, a.paper_dir, a.stage)
    print(f"  {chits} hit(s)")

    print("== terms (warnings: source of every key term, sense clashes; references/concepts.md section 3)")
    th = term_checks(main_path, a.paper_dir, chapters, a.habits_max)
    print(f"  {th} warning(s)")

    print("== vocabulary")
    vh = vocab_checks(main_path, a.paper_dir, a.vocab)
    print(f"  {vh} hit(s)")

    print("== cohesion (soft targets, not counted as hits; prose.md section 4b)")
    cohesion_checks(main_path, a.paper_dir)

    print("== lint")
    hits = 0
    files = chapters + ([main_path] if main_path else [])
    files = [p for p in files if os.path.basename(p) not in LINT_SKIP]
    for p in files:
        raw = read(p)
        if p == main_path:                      # lint the document body only, keep line numbers
            head, sep, tail = raw.partition("\\begin{document}")
            raw = "\n" * head.count("\n") + sep + tail if sep else raw
        body = uncomment(raw)
        rules = [(r, "banned/avoid") for r in BANNED] + [(r, "placeholder left") for r in PLACEHOLDERS]
        rules += [(r"\\vspace\{-[^}]*\}\s*\\(?:sub)*section|\\(?:sub)*section\*?\{[^}]*\}\s*\\vspace\{-",
                   "negative \\vspace at a heading: kits forbid changing the format; keep it inside floats"),
                  (r"\\paragraph\{", "use \\textbf{Head.} run-ins"), (r"[\u2191\u2193]", "Unicode arrow: use $\\uparrow$"),
                  (r"\\begin\{itemize\}(?!\[leftmargin=\*\])", "itemize without [leftmargin=*]"),
                  (r"\\textit\{(?!\\textbf)", "italics: only for a term at its definition; emphasis is bold"),
                  (r"\\emph\{", "italics: only for a term at its definition; emphasis is bold")]
        if venue == "iclr":
            rules += [(r"Equation\s*~?\\eqref", "ICLR: write \\Eqref{}"), (r"(?<![A-Za-z])\\eqref\{", "ICLR: \\eqref prints 'equation 1'; write \\Eqref{}"),
                      (r"\\cite\{", "ICLR: use \\citep{}"), (r"\\citet\{", "ICLR: house style uses \\citep{} only")]
        else:
            rules += [(r"\\Eqref", "non-ICLR: write Equation~\\ref{}")]
        if venue == "icml":
            # icml2026.sty L209 \renewcommand{\cite}[1]{\citep{#1}}: \cite is PARENTHETICAL and fine
            # ("Adam \cite{Adam}" renders "Adam (Doe et al., 2025a)"), but it takes exactly one argument.
            rules += [(r"\\cite\[", "ICML: \\cite takes one argument (the sty maps it to \\citep); write \\citep[p.~3]{x}"),
                      (r"\\(?:resizebox|scalebox)\{[^}]*\}(?:\{[^}]*\})?\{\s*\$",
                       "ICML: never scale math to fit a column; break it with aligned"),
                      # K-ICML26 p3-4: >= 0.1 in before and after captions; icml2026.sty L681 skip=0.1in.
                      (r"\\vspace\{-[^}]*\}\s*\\caption[\[{]",
                       "ICML: negative \\vspace before \\caption; the kit wants >= 0.1 in around captions")]
        if venue == "neurips":
            rules += [(r"\\citep\{", "NeurIPS: house style writes \\cite{} (numeric)")]
        seen = set()
        for pat, why in rules:
            for m in re.finditer(pat, body, flags=re.M):
                line = body.count("\n", 0, m.start()) + 1
                if (line, why) in seen:           # one report per line and rule
                    continue
                seen.add((line, why))
                print(f"  {os.path.relpath(p, a.paper_dir)}:{line}: {why}: {m.group(0)!r}")
                hits += 1
    labels: dict[str, list[str]] = {}
    for p in files:
        for m in re.finditer(r"\\label\{([^}]*)\}", uncomment(read(p))):
            labels.setdefault(m.group(1), []).append(os.path.relpath(p, a.paper_dir))
    for lab, where in sorted(labels.items()):
        if len(where) > 1:
            print(f"  duplicate \\label{{{lab}}} in {', '.join(where)} (latex_source.md section 2.5)")
            hits += 1
    print(f"  {hits} hit(s)")

    print("== intro & contributions (warnings; references/introduction.md IR, contributions.md KR)")
    nic = intro_contrib_checks(main_path, a.paper_dir, a.habits_max)
    print(f"  {nic} warning(s)")

    print("== habits (warnings: recurring draft habits -> plain alternatives; prose.md 'Habits to avoid')")
    nh = habit_checks(files, a.paper_dir, main_path, a.habits_max)
    print(f"  {nh} warning(s)")

    print("== sentences (warnings: length, one subject per sentence, emphasis; prose.md section 12)")
    ns = sentence_checks(main_path, a.paper_dir, a.habits_max)
    print(f"  {ns} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
