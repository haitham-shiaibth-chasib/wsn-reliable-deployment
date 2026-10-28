# Manuscript build

`build_paper.py` writes the IJIES Word manuscript from `results/` and `figures/`. Every number in the
text and tables is read from the result files, so the manuscript always matches the data.

```bash
python manuscript/build_paper.py --template /path/to/IJIES_Format.docx
```

The journal template is not redistributed here; download it from the journal web site
(http://www.inass.org/). Requires `pandoc` (for the Word equations) and `pillow`.
