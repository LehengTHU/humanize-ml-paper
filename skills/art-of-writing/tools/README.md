# Corpus tools: look an expression up

These scripts implement `references/prose.md` "Use attested expressions (lexicon rule)". The skill ships a pre-built phrase index and lexicon (see `../assets/lexicon/`), so `ps.py` works out of the box; you can also build the same kind of index from your own LaTeX sources, in your own workspace, and query that instead. Stdlib Python 3 only.

| Script | What it does |
|---|---|
| `phrase_index.json.gz` | Shipped 1-5 word n-gram counts (no sentence text) over 6 "house" papers (the style this skill imitates) and 16 "reference" papers (two earlier-work lineages, kept only for comparison), grouped `house` / `refA` / `refB`. Built from a private sentence corpus; see `../assets/lexicon/lexicon.md` §1-2 for what it covers |
| `ps.py` | Phrase search. With no `--corpus`, queries the shipped `phrase_index.json.gz`: total occurrences, papers, per-paper counts, per group (`house`, `refA`, `refB`), plus the tier of the phrase. With `--corpus DIR/corpus.jsonl` (built by `build_corpus.py`), queries your own sentences instead: same shape of output, plus rate per 1,000 words, example sentences with file and line, regex (`-r`) and `...` (any words), and a `draft` group with `--draft` |
| `build_corpus.py` | Splits the main text, appendix, captions and statements of each paper into sentences and writes `corpus.jsonl` + `vocab.txt` to `--out DIR`. It follows `\input` files, replaces math with `[M]` / `[EQ]`, citations with `[CITE]`, references with `[REF]`, and refuses to write inside the skill folder |
| `ngrams.py` | Recurring n-grams (by number of papers) or sentence openers of one group of **your own** `corpus.jsonl`, optionally containing a word (there is no ngrams.py equivalent for the shipped index; browse `assets/lexicon/lexicon.md` instead) |

## 1. Look a phrase up in the shipped lexicon (default, no setup)

```bash
python3 tools/ps.py "remains largely unexplored"          # plain phrase, case-insensitive, word boundaries
python3 tools/ps.py "we * that"                             # * = exactly one word
python3 tools/ps.py "is not free" -q                         # -q: counts only
python3 tools/ps.py -g house,refA,refB "compared with"       # -g selects which groups to print (default: all three)
```

Output, per group: total occurrences, how many of the group's papers contain it (`papers 4/6`), and the per-paper counts (`H2:3 H4:1`). For `house` it also prints the tier: **core** = in >= 2 of the 5 most recent house papers (H2-H6); **occasional** = 1; **retired** = only in the oldest house paper (H1); **ref_only** = 0 in house but used in >= 2 of the 16 reference papers combined; **absent** = nowhere. `references/prose.md` "Habits to avoid" and the lexicon's own `banned` tier cover the forms that are dropped regardless of count. Phrases are 1-5 words (the index does not go further); the shipped index stores counts only, not example sentences — for those, look the entry up in `assets/lexicon/lexicon.md` or build your own corpus (below).

## 2. Build your own corpus (optional, to check your own papers)

```bash
# the main .tex of each paper you wrote as first author (::YEAR is optional; it sets what counts as recent)
python3 tools/build_corpus.py --mine ~/papers/a/main.tex::2024 ~/papers/b/main.tex::2025 ~/papers/c/main.tex::2026 \
    --reference ~/papers/admired/main.tex::2025 --out ~/style_corpus
# or list them in a JSON file (paths relative to it)
python3 tools/build_corpus.py --config ~/style_corpus/sources.json --out ~/style_corpus
#   {"papers": [{"key": "A", "group": "mine", "year": 2026, "path": "../papers/a/main.tex"}, ...]}
```

Use `--wrappers coA,coB` if your sources wrap edited text in co-author macros whose text should be kept. Arxiv source tarballs work once unpacked: point `--mine` at the file with `\begin{document}`.

## 3. Search your own corpus

```bash
export STYLE_CORPUS=~/style_corpus/corpus.jsonl       # or pass --corpus each time
python3 tools/ps.py "remains largely unexplored" --corpus $STYLE_CORPUS
python3 tools/ps.py "we * that" -n 5 --corpus $STYLE_CORPUS               # -n examples per group
python3 tools/ps.py "To ... we propose" -q --corpus $STYLE_CORPUS          # ... = any words; -q counts only
python3 tools/ps.py -r "^(However|Nevertheless)," --region main --corpus $STYLE_CORPUS
python3 tools/ps.py "compared with" --draft paper/main.tex --corpus $STYLE_CORPUS   # your current draft as group 'draft'
python3 tools/ngrams.py -g mine --openers --min-papers 2 --corpus $STYLE_CORPUS     # recurring sentence openers
python3 tools/ngrams.py -g mine -n 3,4 --contains gap --min-papers 2 --corpus $STYLE_CORPUS
```

Once `--corpus` points at a real file, `ps.py` reports groups `mine` / `reference` (plus `draft` with `--draft`) instead of `house` / `refA` / `refB`, with the tier rule: **core** = in 2 or more of your recent papers (within `--recent-years`, default 3, of the newest one); **occasional** = 1 recent paper; **retired** = only older papers; **reference only** = only the `reference` group; **absent** = nowhere. Read the printed examples before trusting a count: a hit counts only in the same sense.

## 4. Build your own lexicon

Run `ngrams.py --openers` and `ngrams.py -n 3,4` over `mine`, sort the recurring frames by writing step (background, gap, proposal, mechanism, theory, setup, results, attribution, ablation, pointers, section openers and roadmaps, conclusion and limitations, connectives by function, parenthesis frames), and keep one Markdown table per step in your workspace: expression | function | papers / uses | tier | example. Then draft every sentence from that table, and check anything new with `ps.py` first.

## 5. Word list for check_paper.py

`vocab.txt` (from `build_corpus.py`) holds the lower-case words of your main text. Pass it to the lint: `python3 scripts/check_paper.py <paper_dir> --vocab ~/style_corpus/vocab.txt`.
