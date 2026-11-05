"""Mark the revisions of a manuscript in red, against the submitted version.

Usage
-----
    python manuscript/mark_changes.py --old submitted.docx --new revised.docx --out revised_marked.docx

Every paragraph of the revised document (body text, table cells, captions, references) is matched
with the most similar paragraph of the submitted one. Words that were added or changed are set in red;
unchanged words keep their color. Paragraphs without a counterpart are red throughout, and so are
display equations whose content changed. Pure renumbering of citations, equations, tables, figures
and sections is not marked, because it changes no content. Deleted text is not shown.
"""
from __future__ import annotations

import argparse
import difflib
import re
import shutil
import tempfile
import zipfile

RED = "FF0000"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_TOKEN = re.compile(r"\[[\d,\s\-–]+\]|\(\d+\)(?:[-–]\(\d+\))?|\s+|[A-Za-z0-9α-ωΑ-Ω'’\-–.]+|[^\sA-Za-z0-9α-ωΑ-Ω]", re.U)
_REFNUM = re.compile(r"^\[[\d,\s\-–]+\]$")
_KEYS = {"table", "tables", "fig.", "figs.", "figure.", "section", "sections", "eq.", "eqs.", "algorithm"}


def _tokens(text):
    return [m.group(0) for m in _TOKEN.finditer(text)]


def _norm(tokens):
    """Comparison keys: whitespace dropped, renumbered references mapped to placeholders."""
    out, prev = [], ""
    words = [t for t in tokens if not t.isspace()]
    for wi, t in enumerate(words):
        k = t
        if _REFNUM.match(t) or re.fullmatch(r"\(\d+\)([-–]\(\d+\))?", t):
            k = "<ref>"
        elif prev.lower() in _KEYS and re.fullmatch(r"\d+(\.\d+)?[.,;:)]?", t):
            k = "<n>"
        elif (wi == 0 and re.fullmatch(r"\d+(\.\d+)+\.?|\d+\.", t) and len(words) > 1
              and re.fullmatch(r"[A-Z][A-Za-z\-]*", words[1])):                       # section heading number
            k = "<n>"
        out.append(k)
        prev = t
    return out


def _para_text(p_xml):
    """Text of the w:t runs of a paragraph that are not inside an equation."""
    body = re.sub(r"<m:oMath(?:Para)?\b.*?</m:oMath(?:Para)?>", "", p_xml, flags=re.S)
    return "".join(_unescape(t) for t in re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", body, re.S))


def _unescape(s):
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&")


def _escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _paragraphs(xml):
    return [m for m in re.finditer(r"<w:p[ >].*?</w:p>", xml, re.S)]


def _math_key(m_xml):
    return re.sub(r"\s+", "", "".join(re.findall(r"<m:t[^>]*>(.*?)</m:t>", m_xml, re.S)))


def _redden_rpr(run_xml):
    if "<w:color " in run_xml:
        return re.sub(r'<w:color w:val="[0-9A-Fa-f]{6}"/>', f'<w:color w:val="{RED}"/>', run_xml)
    if "<w:rPr>" in run_xml:
        return run_xml.replace("<w:rPr>", f'<w:rPr><w:color w:val="{RED}"/>', 1)
    return re.sub(r"(<w:r(?: [^>]*)?>)", rf'\1<w:rPr><w:color w:val="{RED}"/></w:rPr>', run_xml, count=1)


def _mark_paragraph(p_xml, flags):
    """Split the text runs of p_xml by the per-character flags and color the flagged parts red."""
    pos = [0]

    def repl(m):
        run = m.group(0)
        tm = re.search(r"(<w:t(?: [^>]*)?>)(.*?)(</w:t>)", run, re.S)
        if not tm:
            return run
        text = _unescape(tm.group(2))
        n = len(text)
        f = flags[pos[0]:pos[0] + n]
        pos[0] += n
        if not any(f):
            return run
        if all(f):
            return _redden_rpr(run)
        pieces, start = [], 0
        for i in range(1, n + 1):
            if i == n or f[i] != f[start]:
                seg = text[start:i]
                new = run[:tm.start(2)] + _escape(seg) + run[tm.end(2):]
                new = new.replace("<w:t>", '<w:t xml:space="preserve">')
                pieces.append(_redden_rpr(new) if f[start] else new)
                start = i
        return "".join(pieces)

    out, last = [], 0
    for m in re.finditer(r"<m:oMath(?:Para)?\b.*?</m:oMath(?:Para)?>|<w:r(?: [^>]*)?>.*?</w:r>", p_xml, re.S):
        out.append(p_xml[last:m.start()])
        out.append(m.group(0) if m.group(0).startswith("<m:") else repl(m))
        last = m.end()
    out.append(p_xml[last:])
    return "".join(out)


def mark(old_docx, new_docx, out_docx, threshold=0.45):
    with zipfile.ZipFile(old_docx) as z:
        old = z.read("word/document.xml").decode("utf8")
    with zipfile.ZipFile(new_docx) as z:
        new = z.read("word/document.xml").decode("utf8")
    def _data_tables(xml):
        """Non-equation tables of a document body (equation layout tables contain m:oMath)."""
        return [m for m in re.finditer(r"<w:tbl>.*?</w:tbl>", xml, re.S) if "<m:oMath" not in m.group(0)]

    def _keyed(paras):
        out = [(_norm(_tokens(t)), t) for t in paras if t.strip()]
        return out, {" ".join(k) for k, _ in out}

    old_tables = []
    for m in _data_tables(old):
        cells = [_para_text(pm.group(0)) for pm in _paragraphs(m.group(0))]
        old_tables.append((_norm(_tokens(" ".join(cells))), _keyed(cells)))
    old_out = old
    for m in reversed(_data_tables(old)):
        old_out = old_out[:m.start()] + old_out[m.end():]
    body_pool = _keyed([_para_text(m.group(0)) for m in _paragraphs(old_out)])
    old_math = {_math_key(m) for m in re.findall(r"<m:oMath>.*?</m:oMath>", old, re.S)}
    stats = dict(paragraphs=0, unchanged=0, edited=0, new=0, equations_new=0, tables_new=0, tables_edited=0)

    def mark_text(p_xml, pool, all_red=False):
        # equations: whole equation red when its content is new
        if "<m:oMath" in p_xml:
            def eqrep(mm):
                key = _math_key(mm.group(0))
                if key in old_math:
                    return mm.group(0)
                stats["equations_new"] += 1
                return re.sub(r"<w:rPr>", f'<w:rPr><w:color w:val="{RED}"/>', mm.group(0))
            p_xml = re.sub(r"<m:oMath>.*?</m:oMath>", eqrep, p_xml, flags=re.S)
        text = _para_text(p_xml)
        if not text.strip():
            return p_xml
        stats["paragraphs"] += 1
        tok = _tokens(text)
        key = _norm(tok)
        old_tok, exact = pool
        if not all_red and " ".join(key) in exact:
            stats["unchanged"] += 1
            return p_xml
        best, best_r = None, 0.0
        if re.match(r"\[\d+\]\t", text):         # a reference is either unchanged or new
            all_red = True
        if not all_red:
            for k, _ in old_tok:
                sm = difflib.SequenceMatcher(None, k, key, autojunk=False)
                if sm.real_quick_ratio() <= best_r or sm.quick_ratio() <= best_r:
                    continue
                r = sm.ratio()
                if r > best_r:
                    best, best_r = k, r
        red_tok = [True] * len(key)
        if best is not None and best_r >= threshold:
            red_tok = [False] * len(key)
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, best, key, autojunk=False).get_opcodes():
                if op in ("replace", "insert"):
                    for j in range(j1, j2):
                        red_tok[j] = True
            stats["edited"] += 1
        else:
            stats["new"] += 1
        flags, ti = [], 0
        tok_flags = []
        for t in tok:
            if t.isspace():
                tok_flags.append(None)
            else:
                tok_flags.append(red_tok[ti])
                ti += 1
        for i, t in enumerate(tok):
            f = tok_flags[i]
            if f is None:                       # a space is red only between two red words
                prev = next((tok_flags[j] for j in range(i - 1, -1, -1) if tok_flags[j] is not None), False)
                nxt = next((tok_flags[j] for j in range(i + 1, len(tok)) if tok_flags[j] is not None), False)
                f = bool(prev and nxt)
            flags += [f] * len(t)
        return _mark_paragraph(p_xml, flags)

    def handle_table(tm):
        t_xml = tm.group(0)
        if "<m:oMath" in t_xml:                 # equation layout table: paragraphs against the body pool
            return re.sub(r"<w:p[ >].*?</w:p>", lambda pm: mark_text(pm.group(0), body_pool), t_xml, flags=re.S)
        cells = [_para_text(pm.group(0)) for pm in _paragraphs(t_xml)]
        key = _norm(_tokens(" ".join(cells)))
        best, best_r = None, 0.0
        for k, pool in old_tables:
            r = difflib.SequenceMatcher(None, k, key, autojunk=False).ratio()
            if r > best_r:
                best, best_r = pool, r
        if best is None or best_r < 0.5:        # a new table is red throughout
            stats["tables_new"] += 1
            return re.sub(r"<w:p[ >].*?</w:p>", lambda pm: mark_text(pm.group(0), body_pool, True), t_xml, flags=re.S)
        stats["tables_edited"] += 1
        return re.sub(r"<w:p[ >].*?</w:p>", lambda pm: mark_text(pm.group(0), best), t_xml, flags=re.S)

    def handle_body(segment):
        return re.sub(r"<w:p[ >].*?</w:p>", lambda pm: mark_text(pm.group(0), body_pool), segment, flags=re.S)

    b0 = new.index("<w:body>")
    rest, parts, last = new[b0:], [], 0
    for tm in re.finditer(r"<w:tbl>.*?</w:tbl>", rest, re.S):
        parts.append(handle_body(rest[last:tm.start()]))
        parts.append(handle_table(tm))
        last = tm.end()
    parts.append(handle_body(rest[last:]))
    marked = new[:b0] + "".join(parts)
    tmp = tempfile.mkdtemp()
    with zipfile.ZipFile(new_docx) as z:
        z.extractall(tmp)
    with open(f"{tmp}/word/document.xml", "w", encoding="utf8") as f:
        f.write(marked)
    with zipfile.ZipFile(out_docx, "w", zipfile.ZIP_DEFLATED) as z:
        import os
        for root, _, files in os.walk(tmp):
            for fn in files:
                full = os.path.join(root, fn)
                z.write(full, os.path.relpath(full, tmp))
    shutil.rmtree(tmp)
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old", required=True, help="submitted manuscript (.docx)")
    ap.add_argument("--new", required=True, help="revised manuscript (.docx)")
    ap.add_argument("--out", required=True, help="revised manuscript with the changes in red (.docx)")
    a = ap.parse_args()
    print(mark(a.old, a.new, a.out))
