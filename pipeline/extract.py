#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Legal due-diligence material extraction layer.

Reads the data-room files (PDF / XLSX / DOCX, or the offline .txt extracted
views used by the bundled demo) and builds a MaterialStore keyed by the stable
"XX.Y" document prefix.  No instance-specific numbers are hardcoded here —
everything is extracted from the files at runtime.

Exposes:
  - Material.text            full extracted text (pdf/docx) or concatenated sheet text (xlsx)
  - Material.sheets          dict[sheet_name] -> list[dict]  (xlsx only)
  - Store.search(pattern)    regex search across all material text
  - Store.get(prefix)        Material by "XX.Y" key
  - Store.facts              normalized structured facts (see build_facts)
"""
import os, re, json, glob, sys
from collections import OrderedDict

# Offline bootstrap: make the vendored pure-python deps importable without pip.
_SUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(_SUB, "vendor"), _SUB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------- low-level readers ------------------------------------------------
def _read_pdf(path):
    from pypdf import PdfReader
    out = []
    r = PdfReader(path)
    for i, pg in enumerate(r.pages, 1):
        t = pg.extract_text() or ""
        out.append(f"[p{i}]\n{t}")
    return "\n".join(out)

def _read_docx(path):
    # stdlib-only reader (no python-docx / lxml) so .docx sources parse offline.
    from _docx import read_docx_text
    text = read_docx_text(path)
    # python-docx also surfaced table cell text; read_docx_text already includes
    # table-cell paragraphs, so no separate table handling is needed.
    return text

def _norm(v):
    if v is None:
        return None
    if hasattr(v, "isoformat"):          # datetime / date
        return v.isoformat()[:10]
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v

def _read_xlsx(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    sheets = OrderedDict()
    full = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        rows = [r for r in rows if any(c is not None and str(c).strip() != "" for c in r)]
        if not rows:
            sheets[ws.title] = []
            continue
        # header detection: row with the most short CJK column-name cells
        def header_score(r):
            s = 0
            for c in r:
                if c is None:
                    continue
                t = str(c).strip()
                if t and len(t) <= 10 and re.search(r"[一-鿿]", t):
                    s += 1
            return s
        best, bscore = 0, -1
        for i, r in enumerate(rows):
            sc = header_score(r)
            if sc > bscore:
                best, bscore = i, sc
        header = [str(h).strip() if h is not None else "" for h in rows[best]]
        recs = []
        for r in rows[best+1:]:
            rec = {header[i]: _norm(r[i] if i < len(r) else None) for i in range(len(header))}
            recs.append(rec)
        sheets[ws.title] = recs
        for rec in recs:
            vals = [f"{k}={v}" for k, v in rec.items() if v not in (None, "")]
            if vals:
                full.append(" ; ".join(vals))
    return sheets, "\n".join(full)

# ---------- txt-extracted view reader (offline demo data room) ------------
# The bundled synthetic demo data room ships as `.txt` extracted views in the
# SAME serialization the offline extractor produces, so the pipeline runs with
# zero binary dependencies. Format (per file):
#   # XLSX: <path>.xlsx
#   ## SHEET: <sheetname>  (rows=R, cols=C)
#   A4=colA | B4=colB | ...        <- header row (short CJK column names)
#   A5=valA | B5=valB | ...        <- data rows
# PDF/DOCX views: `# PDF: <path> (pages=N)` / `# DOCX: ...` followed by body text.
def _looks_like_header(row):
    vals = [v for v in row.values() if v]
    if not vals:
        return False
    score = sum(1 for v in vals if v and len(v) <= 12 and re.search(r"[一-鿿]", v))
    return score >= max(2, len(vals) - 1)

def _parse_txt_sheets(lines):
    sheets = OrderedDict()
    cur = None
    header_cols = None
    for ln in lines[1:]:
        m = re.match(r"^##\s*SHEET:\s*(.+?)\s*\(rows=", ln)
        if m:
            cur = m.group(1).strip()
            sheets[cur] = []
            header_cols = None
            continue
        if cur is None:
            continue
        cells = re.findall(r"([A-Z])(\d+)=(.*?)(?:\s*\|\s*|$)", ln)
        if not cells:
            continue
        row = {c: v.strip() for c, _, v in cells}
        if header_cols is None:
            if _looks_like_header(row):
                header_cols = {c: row[c] for c in row if row[c]}
            continue
        rec = {name: row.get(col, "") for col, name in header_cols.items()}
        sheets[cur].append(rec)
    return sheets

def _read_txt(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        raw = f.read()
    lines = raw.splitlines()
    if not lines:
        return None, ""
    body = "\n".join(lines[1:]) if len(lines) > 1 else ""
    if lines[0].startswith("# XLSX:"):
        return _parse_txt_sheets(lines), body
    # PDF / DOCX view: full body is the extracted text
    return None, body

# ---------- Material --------------------------------------------------------
class Material:
    def __init__(self, prefix, name, path, ext):
        self.prefix = prefix          # e.g. "02.1"
        self.name = name              # full filename stem
        self.path = path
        self.ext = ext
        self.text = ""
        self.sheets = None
        if ext == "pdf":
            self.text = _read_pdf(path)
        elif ext == "docx":
            self.text = _read_docx(path)
        elif ext == "xlsx":
            self.sheets, self.text = _read_xlsx(path)
        elif ext == "txt":
            # Offline txt-extracted view (used for the bundled synthetic demo
            # data room so the pipeline runs with zero binary dependencies).
            self.sheets, self.text = _read_txt(path)

    def search(self, pattern, flags=re.IGNORECASE):
        return [(m.start(), m.group(0)) for m in re.finditer(pattern, self.text, flags)]

    def locate(self, pattern, flags=re.IGNORECASE):
        """Return a citation location string ('第N页' / sheet) for a regex hit."""
        m = re.search(pattern, self.text, flags)
        if not m:
            return ""
        before = self.text[:m.start()]
        pg = re.findall(r"\[p(\d+)\]", before)
        if pg:
            return f"第{pg[-1]}页"
        # xlsx sheet context: find nearest preceding 'sheet=' marker
        sh = re.findall(r"sheet=([^;\n]+)", before)
        if sh:
            return sh[-1].strip()
        return "正文"

    def find_rows(self, sheet, **conds):
        """Return rows in `sheet` whose cells equal/contains the given conds (substring match)."""
        if not self.sheets or sheet not in self.sheets:
            return []
        res = []
        for rec in self.sheets[sheet]:
            ok = True
            for k, v in conds.items():
                cell = rec.get(k)
                if cell is None or str(v) not in str(cell):
                    ok = False
                    break
            if ok:
                res.append(rec)
        return res

# ---------- Store ------------------------------------------------------------
class Store:
    def __init__(self, root):
        self.root = root
        self.by_prefix = OrderedDict()
        self.by_name = {}
        self._load(root)

    def _load(self, root):
        for path in sorted(glob.glob(os.path.join(root, "**", "*"), recursive=True)):
            if not os.path.isfile(path):
                continue
            base = os.path.basename(path)
            ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
            if ext not in ("pdf", "docx", "xlsx", "txt"):
                continue
            # doc prefix "XX.Y" may appear anywhere in the filename
            # (category-prefixed names look like "01_主体__01.2_xxx.txt").
            m = re.search(r"(\d{2}\.\d+)", base)
            prefix = m.group(1) if m else base
            stem = os.path.splitext(base)[0]
            mat = Material(prefix, stem, path, ext)
            self.by_prefix.setdefault(prefix, mat)
            self.by_name[stem] = mat

    def get(self, prefix):
        return self.by_prefix.get(prefix)

    def get_by_name(self, substr):
        for stem, mat in self.by_name.items():
            if substr in stem:
                return mat
        return None

    def search(self, pattern, flags=re.IGNORECASE):
        hits = []
        for mat in self.by_prefix.values():
            for pos, g in mat.search(pattern, flags):
                hits.append((mat.prefix, pos, g))
        return hits

    def all_text(self):
        return "\n".join(m.text for m in self.by_prefix.values())

# ---------- normalized structured facts -------------------------------------
def build_facts(store):
    """Pull instance-specific structured facts. ALL values come from files.
    Returns a dict keyed by role; downstream analyzer templates on these."""
    F = {}
    mat = lambda p: store.get(p)

    # ---- equity / capital (02.1) ----
    cap = mat("02.1")
    if cap and cap.sheets:
        cur = cap.sheets.get("当前股权结构", [])
        equity = []
        for r in cur:
            name = r.get("股东")
            if not name:
                continue
            equity.append({
                "name": str(name),
                "subscribed": r.get("认缴出资（万元）"),
                "paid": r.get("实缴出资（万元）"),
                "ratio": r.get("内部台账持股比例"),
                "deadline": r.get("出资期限"),
                "burden": r.get("权利负担"),
            })
        F["equity_ledger"] = equity

    # ---- articles (01.2) capital/quorum ----
    art = mat("01.2")
    if art:
        t = art.text
        # 股东比例从章程正文抽取（不写死姓名/金额）
        ratios = re.findall(r"([\u4e00-\u9fa5]{2,6})\s*[:：]?\s*(\d+)\s*%", t)
        quorum = re.search(r"(至少|不少于|应当有)\s*(\d+)\s*名?\s*董事", t)
        F["articles"] = {
            "text": t,
            "explicit_ratios": ratios,
            "board_quorum": int(quorum.group(2)) if quorum else None,
        }

    # ---- registration (01.1) ----
    reg = mat("01.1")
    if reg:
        F["registration"] = {"text": reg.text}

    # ---- transfer/proposal docs (02.3) ----
    tr = mat("02.3")
    if tr:
        F["transfer_doc"] = {"text": tr.text}

    # ---- governance resolutions (02.4) ----
    gr = mat("02.4")
    if gr:
        F["gov_resolutions"] = {"text": gr.text}

    # ---- contract ledger (03.1) ----
    cl = mat("03.1")
    if cl and cl.sheets:
        ledger = cl.sheets.get("重大合同台账", [])
        contracts = []
        for r in ledger:
            contracts.append({
                "id": r.get("编号"),
                "party": r.get("相对方"),
                "name": r.get("合同名称/编号"),
                "amount": r.get("合同金额/余额"),
                "status": r.get("履行状态"),
                "coc": r.get("控制权变更"),
                "transfer": r.get("转让/终止"),
                "dispute": r.get("争议/逾期"),
            })
        F["contracts"] = contracts

    # ---- loan (03.4) ----
    loan = mat("03.4")
    if loan:
        F["loan"] = {"text": loan.text}

    # ---- IP list (04.1) ----
    ip = mat("04.1")
    if ip and ip.sheets:
        ipl = ip.sheets.get("知识产权清单", [])
        ips = []
        for r in ipl:
            ips.append({
                "id": r.get("编号"),
                "type": r.get("类型"),
                "name": r.get("名称"),
                "regno": r.get("登记/申请号"),
                "owner": r.get("登记权利人"),
                "status": r.get("状态"),
                "product": r.get("使用产品"),
                "doc": r.get("权属文件"),
            })
        F["ip_list"] = ips

    # ---- opensource (04.4) ----
    osw = mat("04.4")
    if osw and osw.sheets:
        comps = osw.sheets.get("开源组件", [])
        oss = []
        for r in comps:
            oss.append({
                "component": r.get("组件"),
                "license": r.get("许可证"),
                "modified": r.get("是否修改"),
                "network": r.get("网络交互"),
                "distribute": r.get("是否分发"),
                "rating": r.get("内部评级"),
            })
        F["opensource"] = oss

    # ---- employees (05.1) ----
    emp = mat("05.1")
    if emp and emp.sheets:
        roster = emp.sheets.get("员工名册", [])
        summary = emp.sheets.get("汇总", [])
        F["employees"] = {
            "count": len([r for r in roster if r.get("员工编号")]),
            "roster": roster,
            "summary": summary,
        }

    # ---- privacy policy (06.1) ----
    priv = mat("06.1")
    if priv:
        F["privacy"] = {"text": priv.text}

    # ---- cloud bill (06.2) ----
    cb = mat("06.2")
    if cb and cb.sheets:
        region = cb.sheets.get("资源区域", [])
        regions = []
        for r in region:
            regions.append({
                "group": r.get("资源组"),
                "service": r.get("服务"),
                "region": r.get("地域"),
                "env": r.get("环境标签"),
                "usage": r.get("用途"),
                "data_desc": r.get("数据说明"),
            })
        F["cloud_regions"] = regions

    # ---- disputes (07.1) ----
    disp = mat("07.1")
    if disp and disp.sheets:
        dlist = disp.sheets.get("争议清单", [])
        cont = disp.sheets.get("或有负债", [])
        F["disputes"] = {
            "list": [{"id": r.get("编号"), "matter": r.get("事项"), "party": r.get("对方"),
                      "status": r.get("程序状态"), "amount": r.get("争议金额"),
                      "exposure": r.get("预计敞口")} for r in dlist],
            "contingent": [{"id": r.get("编号"), "type": r.get("类型"), "party": r.get("相对方"),
                            "amount": r.get("本金/主张金额"), "judgment": r.get("当前判断")} for r in cont],
        }

    # ---- license (06.3) ----
    lic = mat("06.3")
    if lic:
        F["license_doc"] = {"text": lic.text}

    # ---- lease (08.1) ----
    lease = mat("08.1")
    if lease:
        F["lease"] = {"text": lease.text}

    # ---- org / affiliates (01.3) ----
    org = mat("01.3")
    if org and org.sheets:
        orgs = org.sheets.get("组织架构", [])
        F["affiliates"] = [{"name": r.get("主体名称"), "relation": r.get("关系"),
                             "ratio": r.get("持股/控制比例"), "biz": r.get("主要业务"),
                             "note": r.get("备注")} for r in orgs]

    return F

if __name__ == "__main__":
    import sys, os
    _here = os.path.dirname(os.path.abspath(__file__))
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_here, "..", "materials")
    s = Store(root)
    f = build_facts(s)
    print("materials:", len(s.by_prefix))
    print("equity_ledger:", json.dumps(f.get("equity_ledger", []), ensure_ascii=False)[:400])
    print("contracts:", len(f.get("contracts", [])), "disputes:", len(f.get("disputes", {}).get("list", [])))
    print("cloud_regions sample:", json.dumps(f.get("cloud_regions", [])[:3], ensure_ascii=False)[:300])
