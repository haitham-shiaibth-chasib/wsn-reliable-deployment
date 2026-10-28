"""Minimal WordprocessingML writer that fills the IJIES template.

Body text 11 pt Times New Roman, tables/captions 10 pt, two-column body,
display equations as native Word equations (OMML) numbered on the right.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from xml.sax.saxutils import escape

from PIL import Image

TNR = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'
COL_TW = 4657                       # one column of the template, in twips
EMU_PER_CM = 360000


def _rpr(size=22, b=False, i=False, va=None, color=None):
    s = TNR
    if b:
        s += "<w:b/><w:bCs/>"
    if i:
        s += "<w:i/><w:iCs/>"
    if color:
        s += f'<w:color w:val="{color}"/>'
    s += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    if va:
        s += f'<w:vertAlign w:val="{va}"/>'
    return f"<w:rPr>{s}</w:rPr>"


def run(text, size=22, b=False, i=False, va=None, color=None):
    if text == "":
        return ""
    return f'<w:r>{_rpr(size, b, i, va, color)}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def _math_runs(expr, size, b=False):
    """Italic inline math with _x / _{..} subscripts and ^x / ^{..} superscripts.
    Subscript words of 2+ letters are set upright (labels such as 'cov')."""
    out, i = [], 0
    while i < len(expr):
        ch = expr[i]
        if ch in "_^" and i + 1 < len(expr):
            va = "subscript" if ch == "_" else "superscript"
            if expr[i + 1] == "{":
                j = expr.index("}", i + 2)
                tok = expr[i + 2:j]
                i = j + 1
            else:
                m = re.match(r"[A-Za-z0-9]+", expr[i + 1:])
                tok = m.group(0) if m else expr[i + 1]
                i += 1 + len(tok)
            upright = len(tok) > 1 and tok.isalpha()
            has_letter = bool(re.search(r"[A-Za-zα-ωΑ-Ω]", tok))
            out.append(run(tok, size, b, i=has_letter and not upright, va=va))
            continue
        j = i
        while j < len(expr) and expr[j] not in "_^":
            j += 1
        seg = expr[i:j]
        # italicise letters, keep digits/operators/parentheses/Greek upright-able as italic too
        for part in re.split(r"(\s+|[0-9.,()=≤≥<>+−\-/|\[\]×·√∑∫]+)", seg):
            if part:
                ital = bool(re.search(r"[A-Za-zα-ωΑ-Ω]", part))
                out.append(run(part, size, b, i=ital))
        i = j
    return "".join(out)


def rich(text, size=22, b=False, color=None):
    """Inline markup: {{math}} italic math, **bold**, plain text otherwise."""
    out = []
    for tok in re.split(r"(\{\{.*?\}\}|\*\*.*?\*\*)", text):
        if not tok:
            continue
        if tok.startswith("{{"):
            out.append(_math_runs(tok[2:-2], size, b))
        elif tok.startswith("**"):
            out.append(run(tok[2:-2], size, True, color=color))
        else:
            out.append(run(tok, size, b, color=color))
    return "".join(out)


def para(inner, jc="both", first_line=330, before=0, after=0, keep_next=False, ind_left=0, hanging=0,
         line=240, keep_lines=False):
    ppr = '<w:pPr><w:pStyle w:val="ac"/>'
    if keep_next:
        ppr += "<w:keepNext/>"
    if keep_lines:
        ppr += "<w:keepLines/>"
    ppr += f'<w:spacing w:before="{before}" w:after="{after}" w:line="{line}" w:lineRule="auto"/>'
    ind = ""
    if first_line:
        ind += f' w:firstLine="{first_line}"'
    if ind_left:
        ind += f' w:left="{ind_left}"'
    if hanging:
        ind += f' w:hanging="{hanging}"'
    if ind:
        ppr += f"<w:ind{ind}/>"
    ppr += f'<w:jc w:val="{jc}"/></w:pPr>'
    return f"<w:p>{ppr}{inner}</w:p>"


def body(text):
    return para(rich(text))


def heading1(text):
    return para(run(text, 24, True), jc="left", first_line=0, before=240, after=120, keep_next=True)


def heading2(text):
    return para(run(text, 22, True), jc="left", first_line=0, before=120, after=60, keep_next=True)


def caption(text, keep_next=False, before=60, after=120):
    return para(rich(text, 20), jc="center", first_line=0, before=before, after=after, keep_next=keep_next)


def blank(size=22):
    return f'<w:p><w:pPr><w:pStyle w:val="ac"/><w:spacing w:before="0" w:after="0"/><w:rPr><w:sz w:val="{size}"/></w:rPr></w:pPr></w:p>'


class Doc:
    def __init__(self, template):
        self.template = template
        self.author = "Haitham Shiaibth Chasib"
        self.parts = []
        self.images = []                 # (rid, src path)
        self.eq_count = 0
        self.fig_count = 0
        self.tab_count = 0
        self._pending_eqs = []
        self._docpr = 100

    # ------------------------------------------------------------------ blocks
    def add(self, xml):
        if self._pending_eqs and not xml.startswith("__EQBLOCK__"):
            self.flush_eqs()
        self.parts.append(xml)

    def p(self, text):
        self.add(body(text))

    def h1(self, text):
        self.add(heading1(text))

    def h2(self, text):
        self.add(heading2(text))

    def figure(self, path, cap, width_cm=None):
        self.fig_count += 1
        rid = f"rIdFig{self.fig_count}"
        self.images.append((rid, path))
        w, h = Image.open(path).size
        if width_cm is None:                       # native size at 300 dpi keeps 10 pt lettering
            width_cm = min(w / 300 * 2.54, 7.9)
        cx = int(width_cm * EMU_PER_CM)
        cy = int(cx * h / w)
        self._docpr += 1
        drawing = (
            f'<w:r><w:rPr><w:noProof/></w:rPr><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{self._docpr}" name="Figure {self.fig_count}"/>'
            '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:nvPicPr><pic:cNvPr id="{self._docpr}" name="fig{self.fig_count}.png"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')
        self.add(para(drawing, jc="center", first_line=0, before=120, after=0, keep_next=True))
        self.add(caption(f"Figure. {self.fig_count} {cap}", after=160))
        return self.fig_count

    def table(self, cap, rows, widths, header_rows=1, align=None, size=20, mono_first=False):
        """Three-line table, 10 pt, kept on one page."""
        self.tab_count += 1
        self.add(caption(f"Table {self.tab_count}. {cap}", keep_next=True, before=120, after=60))
        total = sum(widths)
        top = '<w:top w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        bot = '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        thin = '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        xml = (f'<w:tbl><w:tblPr><w:tblW w:w="{total}" w:type="dxa"/><w:jc w:val="center"/>'
               '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="57" w:type="dxa"/><w:right w:w="57" w:type="dxa"/></w:tblCellMar>'
               '</w:tblPr><w:tblGrid>' + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>")
        n = len(rows)
        for ri, row in enumerate(rows):
            xml += '<w:tr><w:trPr><w:cantSplit/>' + ('<w:tblHeader/>' if ri < header_rows else '') + '</w:trPr>'
            for ci, cell in enumerate(row):
                b = ""
                if ri == 0:
                    b += top
                if ri == header_rows - 1:
                    b += thin
                if ri == n - 1:
                    b += bot
                jc = (align[ci] if align else ("left" if ci == 0 else "center"))
                lines = cell.split("\n")
                inner = "".join(
                    f'<w:p><w:pPr><w:keepNext/><w:spacing w:before="10" w:after="10" w:line="230" w:lineRule="auto"/>'
                    f'<w:jc w:val="{jc}"/></w:pPr>{rich(ln, size, b=(ri < header_rows))}</w:p>' for ln in lines)
                xml += (f'<w:tc><w:tcPr><w:tcW w:w="{widths[ci]}" w:type="dxa"/>'
                        f'<w:tcBorders>{b}</w:tcBorders><w:vAlign w:val="center"/></w:tcPr>{inner}</w:tc>')
            xml += "</w:tr>"
        xml += "</w:tbl>"
        self.add(xml)
        self.add(para("", first_line=0, after=60))
        return self.tab_count

    # ------------------------------------------------------------------ equations
    def eq(self, latex):
        """Queue a display equation; consecutive equations share one block."""
        self.eq_count += 1
        self._pending_eqs.append((latex, self.eq_count))
        return self.eq_count

    def flush_eqs(self):
        if not self._pending_eqs:
            return
        self.add(f"__EQBLOCK__{len(self.parts)}__")
        self._eqblocks = getattr(self, "_eqblocks", {})
        self._eqblocks[len(self.parts) - 1] = list(self._pending_eqs)
        self._pending_eqs = []

    def _render_equations(self):
        blocks = getattr(self, "_eqblocks", {})
        if not blocks:
            return
        allq = [(k, i, lt) for k, eqs in blocks.items() for i, (lt, _) in enumerate(eqs)]
        md = "\n\n".join(f"$${lt}$$" for _, _, lt in allq)
        tmp = tempfile.mkdtemp()
        with open(os.path.join(tmp, "e.md"), "w") as f:
            f.write(md)
        subprocess.run(["pandoc", os.path.join(tmp, "e.md"), "-o", os.path.join(tmp, "e.docx")], check=True)
        with zipfile.ZipFile(os.path.join(tmp, "e.docx")) as z:
            dx = z.read("word/document.xml").decode("utf8")
        maths = re.findall(r"<m:oMath>.*?</m:oMath>", dx, re.S)
        assert len(maths) == len(allq), (len(maths), len(allq))
        wr = '<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr>'
        maths = [re.sub(r"(<m:r>(?:<m:rPr>.*?</m:rPr>)?)(<m:t)", lambda m: m.group(1) + wr + m.group(2), mm, flags=re.S)
                 for mm in maths]

        def fix_order(x):
            # schema order: dPr = begChr, sepChr, endChr, grow ; mcPr = count, mcJc
            x = re.sub(r'(<m:begChr[^>]*/>)(<m:endChr[^>]*/>)(<m:sepChr[^>]*/>)', r'\1\3\2', x)
            x = re.sub(r'(<m:endChr[^>]*/>)(<m:sepChr[^>]*/>)', r'\2\1', x)
            x = re.sub(r'(<m:mcJc[^>]*/>)(<m:count[^>]*/>)', r'\2\1', x)
            return x
        maths = [fix_order(mm) for mm in maths]
        it = iter(maths)
        for k, eqs in blocks.items():
            rows = ""
            for latex, num in eqs:
                om = next(it)
                left = (f'<w:p><w:pPr><w:keepNext/><w:spacing w:before="40" w:after="40"/><w:ind w:left="283"/><w:jc w:val="left"/></w:pPr>'
                        f'<m:oMathPara><m:oMathParaPr><m:jc m:val="left"/></m:oMathParaPr>{om}</m:oMathPara></w:p>')
                right = (f'<w:p><w:pPr><w:spacing w:before="40" w:after="40"/><w:jc w:val="right"/></w:pPr>'
                         f'{run(f"({num})", 22)}</w:p>')
                rows += (f'<w:tr><w:trPr><w:cantSplit/></w:trPr><w:tc><w:tcPr><w:tcW w:w="{COL_TW - 560}" w:type="dxa"/><w:vAlign w:val="center"/></w:tcPr>{left}</w:tc>'
                         f'<w:tc><w:tcPr><w:tcW w:w="560" w:type="dxa"/><w:vAlign w:val="center"/></w:tcPr>{right}</w:tc></w:tr>')
            tbl = (f'<w:tbl><w:tblPr><w:tblW w:w="{COL_TW}" w:type="dxa"/>'
                   '<w:tblBorders><w:top w:val="nil"/><w:left w:val="nil"/><w:bottom w:val="nil"/><w:right w:val="nil"/>'
                   '<w:insideH w:val="nil"/><w:insideV w:val="nil"/></w:tblBorders><w:tblLayout w:type="fixed"/>'
                   '<w:tblCellMar><w:left w:w="0" w:type="dxa"/><w:right w:w="0" w:type="dxa"/></w:tblCellMar></w:tblPr>'
                   f'<w:tblGrid><w:gridCol w:w="{COL_TW - 560}"/><w:gridCol w:w="560"/></w:tblGrid>{rows}</w:tbl>')
            self.parts[k] = blank() + tbl + blank()

    # ------------------------------------------------------------------ assembly
    def save(self, out, front_xml):
        self.flush_eqs()
        self._render_equations()
        tmp = tempfile.mkdtemp()
        with zipfile.ZipFile(self.template) as z:
            z.extractall(tmp)
        dpath = os.path.join(tmp, "word", "document.xml")
        d = open(dpath, encoding="utf8").read()
        bstart = d.index("<w:body>") + len("<w:body>")
        paras = list(re.finditer(r"<w:p[ >].*?</w:p>", d[bstart:], re.S))
        keep = {i: d[bstart + m.start(): bstart + m.end()] for i, m in enumerate(paras[:15])}
        sect2 = re.findall(r"<w:sectPr[^>]*>(?:(?!<w:sectPr).)*?<w:cols w:num=\"2\".*?</w:sectPr>", d, re.S)[0]
        sect2 = re.sub(r"<w:type w:val=\"continuous\"/>", '<w:type w:val="continuous"/>', sect2)
        front = front_xml(keep)
        new_body = front + "".join(self.parts) + sect2
        d = d[:bstart] + new_body + "</w:body></w:document>"
        if 'xmlns:m=' not in d[:3000]:
            d = d.replace("<w:document ", '<w:document xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" ', 1)
        open(dpath, "w", encoding="utf8").write(d)
        # document properties: the authors' own, not the template's
        cpath = os.path.join(tmp, "docProps", "core.xml")
        if os.path.exists(cpath):
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            c = open(cpath, encoding="utf8").read()
            c = re.sub(r"<dc:creator>.*?</dc:creator>", f"<dc:creator>{escape(self.author)}</dc:creator>", c)
            c = re.sub(r"<cp:lastModifiedBy>.*?</cp:lastModifiedBy>", f"<cp:lastModifiedBy>{escape(self.author)}</cp:lastModifiedBy>", c)
            c = re.sub(r"<cp:revision>.*?</cp:revision>", "<cp:revision>1</cp:revision>", c)
            c = re.sub(r"(<dcterms:created[^>]*>).*?(</dcterms:created>)", rf"\g<1>{now}\g<2>", c)
            c = re.sub(r"(<dcterms:modified[^>]*>).*?(</dcterms:modified>)", rf"\g<1>{now}\g<2>", c)
            open(cpath, "w", encoding="utf8").write(c)
        # images
        rels = os.path.join(tmp, "word", "_rels", "document.xml.rels")
        r = open(rels, encoding="utf8").read()
        os.makedirs(os.path.join(tmp, "word", "media"), exist_ok=True)
        add = ""
        for rid, src in self.images:
            name = f"paperfig_{rid}.png"
            shutil.copy(src, os.path.join(tmp, "word", "media", name))
            add += (f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                    f'Target="media/{name}"/>')
        r = r.replace("</Relationships>", add + "</Relationships>")
        open(rels, "w", encoding="utf8").write(r)
        ct = os.path.join(tmp, "[Content_Types].xml")
        c = open(ct, encoding="utf8").read()
        if 'Extension="png"' not in c:
            c = c.replace("<Default ", '<Default Extension="png" ContentType="image/png"/><Default ', 1)
        open(ct, "w", encoding="utf8").write(c)
        if os.path.exists(out):
            os.remove(out)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(tmp):
                for fn in files:
                    full = os.path.join(root, fn)
                    arc = os.path.relpath(full, tmp)
                    z.write(full, arc)
        return out
