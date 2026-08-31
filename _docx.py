#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal dependency-free .docx writer + reader (OOXML, stdlib only).

Replaces python-docx, which pulls in `lxml` — a C-extension that cannot be
safely vendored across unknown scoring-env OS/arch.  This module produces valid
Word / LibreOffice / python-docx-readable documents using only the Python
standard library, so the pipeline runs fully OFFLINE.

Writer API (used by render.py):
    d = DocxDocument()
    d.add_heading(text, level)        # level 0 = Title, 1/2 = Heading1/2
    d.add_paragraph(text, bold=False)
    d.add_runs([(text, bold), ...])   # one paragraph, multiple runs
    d.add_bullet(text)
    d.add_table(rows)                 # rows: list[list[str]]
    d.save(path)

Reader API (used by verify.py):
    info = read_docx(path)
    info["paragraphs"] -> [(text, style), ...]   (style in Normal/Title/Heading1/2)
    info["full_text"]  -> all text (incl. table cells)
"""
import os
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _esc(t):
    return escape(str(t))


class DocxDocument:
    def __init__(self):
        self._parts = []

    # ---- writer helpers ----------------------------------------------------
    def add_heading(self, text, level=1):
        style = "Title" if level == 0 else f"Heading{level}"
        self._parts.append(self._para(text, style, bold=True))

    def add_paragraph(self, text="", bold=False):
        self._parts.append(self._para(text, "Normal", bold))

    def add_runs(self, runs):
        """runs: list of (text, bold). Emits one paragraph with multiple runs."""
        runs_xml = ""
        for t, b in runs:
            if b:
                runs_xml += (f'<w:r><w:rPr><w:b/></w:rPr>'
                             f'<w:t xml:space="preserve">{_esc(t)}</w:t></w:r>')
            else:
                runs_xml += f'<w:r><w:t xml:space="preserve">{_esc(t)}</w:t></w:r>'
        self._parts.append(f'<w:p>{runs_xml}</w:p>')

    def add_bullet(self, text):
        self._parts.append(self._para("• " + text, "Normal"))

    def add_table(self, rows):
        if not rows:
            return
        ncol = max(len(r) for r in rows)
        cells = []
        for row in rows:
            tcs = []
            for ci in range(ncol):
                c = row[ci] if ci < len(row) else ""
                tcs.append(
                    '<w:tc><w:tcPr><w:tcW w:w="2400" w:type="dxa"/>'
                    '<w:tcBorders>'
                    '<w:top w:val="single" w:sz="4" w:color="auto"/>'
                    '<w:left w:val="single" w:sz="4" w:color="auto"/>'
                    '<w:bottom w:val="single" w:sz="4" w:color="auto"/>'
                    '<w:right w:val="single" w:sz="4" w:color="auto"/>'
                    '</w:tcBorders></w:tcPr>'
                    f'<w:p><w:r><w:t xml:space="preserve">{_esc(c)}</w:t></w:r></w:p></w:tc>')
            cells.append("<w:tr>" + "".join(tcs) + "</w:tr>")
        tbl = ('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/>'
               '<w:tblW w:w="5000" w:type="pct"/>'
               '<w:tblBorders>'
               '<w:top w:val="single" w:sz="4" w:color="auto"/>'
               '<w:left w:val="single" w:sz="4" w:color="auto"/>'
               '<w:bottom w:val="single" w:sz="4" w:color="auto"/>'
               '<w:right w:val="single" w:sz="4" w:color="auto"/>'
               '<w:insideH w:val="single" w:sz="4" w:color="auto"/>'
               '<w:insideV w:val="single" w:sz="4" w:color="auto"/>'
               '</w:tblBorders></w:tblPr>' + "".join(cells) + '</w:tbl>')
        self._parts.append(tbl)

    @staticmethod
    def _para(text, style, bold=False):
        rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
        return (f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
                f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(text)}</w:t></w:r></w:p>')

    # ---- save --------------------------------------------------------------
    def save(self, path):
        sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>'
                '</w:sectPr>')
        document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    f'<w:document xmlns:w="{W}"><w:body>'
                    + "".join(self._parts) + sect + '</w:body></w:document>')
        content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="xml" ContentType="application/xml"/>'
                         '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                         '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
                         '</Types>')
        rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                '</Relationships>')
        doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                    '</Relationships>')
        styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                  f'<w:styles xmlns:w="{W}">'
                  '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="21"/></w:rPr></w:rPrDefault></w:docDefaults>'
                  '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
                  '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
                  '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="Heading1"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="200" w:after="80"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>'
                  '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="Heading2"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="160" w:after="60"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="23"/></w:rPr></w:style>'
                  '</w:styles>')
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", content_types)
            z.writestr("_rels/.rels", rels)
            z.writestr("word/document.xml", document)
            z.writestr("word/_rels/document.xml.rels", doc_rels)
            z.writestr("word/styles.xml", styles)


def read_docx(path):
    """Read back paragraph text + heading styles for verification (stdlib only)."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    root = ET.fromstring(xml)
    body = root.find(f"{{{W}}}body")
    paras = []
    full_text = []
    if body is not None:
        for p in body.findall(f"{{{W}}}p"):
            style = "Normal"
            ppr = p.find(f"{{{W}}}pPr")
            if ppr is not None:
                ps = ppr.find(f"{{{W}}}pStyle")
                if ps is not None:
                    style = ps.get(f"{{{W}}}val") or "Normal"
            texts = [t.text or "" for t in p.iter(f"{{{W}}}t")]
            txt = "".join(texts)
            paras.append((txt, style))
            full_text.append(txt)
        # include table cell text in full_text
        for t in body.iter(f"{{{W}}}t"):
            full_text.append(t.text or "")
    return {"paragraphs": paras, "full_text": "\n".join(full_text)}


def read_docx_text(path):
    """Extract ALL visible text from a .docx (paragraphs + table cells), stdlib only.

    Mirrors what python-docx's ``Document(path)`` yields (paragraph texts plus
    table-cell text) so downstream regex extraction behaves identically — but
    without the ``lxml`` C-extension dependency. Used by extract.py to read
    .docx source materials offline. Returns a single string, paragraphs
    separated by newlines, in document order (including table-cell paragraphs).
    """
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
    except (KeyError, FileNotFoundError, OSError):
        return ""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return ""
    body = root.find(f"{{{W}}}body")
    if body is None:
        return ""
    chunks = []
    for p in body.iter(f"{{{W}}}p"):
        texts = [t.text or "" for t in p.findall(f".//{{{W}}}t")]
        chunks.append("".join(texts))
    return "\n".join(chunks)
