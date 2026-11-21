# The prompt

The complete task that Claude Opus 5.5 received, verbatim except that the skill's path is shortened to `<skill>/` and the working folder to `<paper>/`.

```text
You are writing a complete ICML submission from scratch, in one session, with the paper-writing skill at <skill> (read its SKILL.md first and follow its workflow, Steps 0 to 7, reading each reference file at the step that names it). Your working folder is the current directory, <paper>; put every file of the paper project there.

1. Idea. Choose the research idea yourself: one original, specific machine-learning method (not a survey or a position paper) that fits one of the skill's paper types. It must be testable with real experiments that you run here: a CPU-only machine (15 cores, 48 GB RAM, no GPU), at most about 45 minutes of compute in total, on synthetic data or small public datasets you can download. Python 3 has numpy and scipy; create a virtual environment in .venv inside this folder and pip install anything else you need (matplotlib for the plots, scikit-learn or a CPU build of torch if the method needs them).

2. Experiments. Put the experiment code in code/ and its raw outputs in results/. Every number in the paper must come from those outputs. Never invent or estimate a number: if an experiment cannot be run, leave its table cells as \pend and say so, as the skill prescribes.

3. Venue and template. Follow the skill's Step 0 for ICML: check the current call for papers, fetch the latest official ICML style kit (templates/venue/icml/README.md), use the skill's ICML skeleton (templates/main_skeleton_icml.tex, templates/chapters_icml/ renamed to chapters/, templates/preamble.tex), and write an anonymous submission with the Impact Statement and an appendix.

4. Figures and tables. Draw the method diagram in TikZ on templates/housediagram.sty and build it with scripts/render_diagram.py --check; make the result plots with templates/plot_style.py from the files in results/; build the tables from templates/tables.tex.

5. References. Cite only real papers. Check each one on the web (arXiv or DBLP) before you add it, and format the .bib as the skill says (scripts/bib_to_dblp.py).

6. Build and check. Compile with tectonic until there are no errors, no undefined references and no overfull boxes; the main text must end exactly at the bottom of page 8 (references, Impact Statement and appendix after it). Run python3 <skill>/scripts/check_paper.py . --venue icml --stage submission and fix what it reports, as the skill's Step 7 describes. Look at the rendered pages (for example with PyMuPDF) and fix what you see.

7. Deliverables. The compiled PDF in this folder, and NOTES.md with: the title and the idea in one paragraph, the experiments you ran and how long they took, which numbers come from which result file, and the final check_paper.py summary.

Rules: work only inside this folder (you may read the skill folder; never modify it). Do not use git. Finish only when the PDF builds cleanly and the checks are addressed.
```
