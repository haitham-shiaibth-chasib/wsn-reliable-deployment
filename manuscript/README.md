# Manuscript build

`build_paper.py` writes the IJIES Word manuscript from `results/` and `figures/`. Every number in the
text and tables is read from the result files, so the manuscript always matches the data.

```bash
python manuscript/build_paper.py --template /path/to/IJIES_Format.docx
```

The journal template is not redistributed here; download it from the journal web site
(http://www.inass.org/). Requires `pandoc` (for the Word equations) and `pillow`.

`mark_changes.py` compares a revised manuscript with the submitted one and sets every added or changed
word in red (new paragraphs and changed display equations entirely), as journals ask for revisions.
Renumbered citations, equations, tables and figures are not marked.

```bash
python manuscript/mark_changes.py --old submitted.docx --new revised.docx --out revised_marked.docx
```
