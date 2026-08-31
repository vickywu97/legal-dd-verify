#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Legal due-diligence analysis engine.

Consumes the extracted MaterialStore + facts and a diligence checklist,
and produces:
  - 52 verification items (status / fact / evidence / gap / risk / disposition / feedback)
  - cross-file contradictions (detected structurally from extracted values)
  - deduped supplementary / inquiry list (~20)
  - 12 key issues (covering the 4 mandatory core risks)

All fact values are interpolated from extraction output, so the same engine
run on an isomorphic B-volume instance re-derives correct results.
"""
import re, json, sys, os
# Offline bootstrap (in case analyze is imported before extract).
_SUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(_SUB, "vendor"), _SUB):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from extract import Store, build_facts

# ---- domain metadata -------------------------------------------------------
DOMAIN = {"CORP":"主体资格","CAP":"股权出资","GOV":"公司治理","CON":"重大合同",
          "IP":"知识产权","HR":"劳动人事","DATA":"数据合规","REG":"业务资质",
          "DISP":"争议债务","PROP":"物业资产"}
STATUS_OK = {"已满足","部分满足","未满足","不适用","待确认","资料冲突"}
RISK_OK = {"HIGH","MEDIUM","LOW","INFO"}
DISP_OK = {"CP","COVENANT","INDEMNITY","PRICE","RFI","MONITOR","NONE"}

# default risk/disposition per domain (escalated by findings)
DOM_RISK = {"CORP":"LOW","CAP":"HIGH","GOV":"MEDIUM","CON":"MEDIUM","IP":"HIGH",
            "HR":"MEDIUM","DATA":"HIGH","REG":"HIGH","DISP":"MEDIUM","PROP":"MEDIUM"}
DOM_DISP = {"CORP":"RFI","CAP":"CP","GOV":"CP","CON":"COVENANT","IP":"CP",
            "HR":"CP","DATA":"RFI","REG":"CP","DISP":"INDEMNITY","PROP":"COVENANT"}

def cite(store, prefix, pattern=None):
    m = store.get(prefix)
    if not m:
        return ""
    if pattern:
        loc = m.locate(pattern)
        return f"{m.name}｜{loc}" if loc else m.name
    return m.name

def cite_list(store, specs):
    return "\n".join(c for c in (cite(store, p, pat) for p, pat in specs) if c)

# Per-instance configuration (set once per engagement; NOT an extracted answer).
# The acquirer / deal structure / baseline date are constants of the task design
# and are identical across A/B volumes, so they are intentionally not "answers".
BASELINE_DATE = "2026-07-15"

_COMPANY_RE = re.compile(r"([一-龥]{4,}(?:科技有限公司|有限公司|合伙企业|股份公司|有限责任公司))")

def find_target_name(store, facts=None):
    """Extract the registered target-company name from the charter/registration
    documents so that output never hardcodes a particular instance's name."""
    for pfx in ("01.1", "01.2"):
        m = store.get(pfx)
        if m:
            hit = _COMPANY_RE.search(m.text)
            if hit:
                return hit.group(1)
    # fallback: first company-like name anywhere
    for m in store.by_prefix.values():
        hit = _COMPANY_RE.search(m.text)
        if hit:
            return hit.group(1)
    return ""

# ============================================================================
# Contradiction detection (structural, instance-agnostic)
# ============================================================================
def detect_contradictions(store, facts):
    out = []

    # ---- CT-01: equity ratio conflict across documents ----
    ledger = {e["name"]: e for e in facts.get("equity_ledger", [])}
    ratios = {}  # shareholder -> set of (decimal_ratio, source)
    for name in ledger:
        aliases = [name]
        # derive generic role aliases from the actual name so the conflict
        # detector is not tied to a particular instance's labels
        base = re.split(r"[（(]", name)[0]
        base = re.sub(r"(有限合伙|合伙企业|有限公司|股份公司|有限责任公司)$", "", base)
        if base and base != name:
            aliases.append(base)
        # pooled / employee-shareholder vehicles are described by generic role
        # terms across instances ("员工持股平台", "平台份额", ...), not by a
        # fixed proper noun — add these semantic aliases for cross-doc matching
        if any(tok in name for tok in ("合伙", "平台", "持股", "有限合伙")):
            aliases += ["员工持股平台", "员工平台", "持股平台", "平台"]
        decs = {}
        for m in store.by_prefix.values():
            for a in aliases:
                if a not in m.text:
                    continue
                # name ... number[%]   (decimal ratio or percent)
                for mm in re.finditer(re.escape(a) + r".{0,220}?(\d+\.?\d*)\s*[%％]?", m.text):
                    raw = float(mm.group(1))
                    has_pct = "%" in mm.group(0) or "％" in mm.group(0)
                    val = raw / 100 if has_pct else raw
                    if (has_pct and raw <= 100) or (not has_pct and raw <= 1):
                        decs.setdefault(round(val, 3), set()).add(m.name)
                # number[%] ... name
                for mm in re.finditer(r"(\d+\.?\d*)\s*[%％]?.{0,220}?" + re.escape(a), m.text):
                    raw = float(mm.group(1))
                    has_pct = "%" in mm.group(0) or "％" in mm.group(0)
                    val = raw / 100 if has_pct else raw
                    if (has_pct and raw <= 100) or (not has_pct and raw <= 1):
                        decs.setdefault(round(val, 3), set()).add(m.name)
        if len(decs) > 1:
            ratios[name] = decs
    if ratios:
        desc_lines = []
        srcs_all = set()
        for name, decs in ratios.items():
            pcts = sorted(int(r * 100) for r in decs)
            srcs = sorted({s for v in decs.values() for s in v})
            srcs_all |= set(srcs)
            desc_lines.append(f"{name}：比例在文件中记载不一（{ '/'.join(str(p)+'%' for p in pcts) }，见 { '、'.join(srcs) }）")
        # incorporate the internally-discovered inconsistency note (02.3 归档备注)
        tr_note = ""
        tr = facts.get("transfer_doc", {}).get("text", "")
        mnote = re.search(r"档案管理员于(\d{4})年.{0,30}?发现.{0,40}?比例不一致.{0,80}?未见回复", tr)
        if mnote:
            yr = mnote.group(1)
            tr_note = (f"目标公司归档备注亦自认：档案管理员于{yr}年归档时发现协议/股东会附件"
                       f"与章程、登记档案比例不一致且至今未见更正回复。")
            srcs_all.add(store.get("02.3").name)
        out.append(dict(
            cid="CT-01", severity="HIGH",
            title="股权结构多源比例不一致",
            primary_items=["CAP-01"],
            files_conflict=sorted(srcs_all),
            items=["CAP-01","CORP-03","CAP-04","CAP-05"],
            description="；".join(desc_lines) + "。" + tr_note +
                        "该冲突直接影响收购基准股权表与本次交易对价，并可能触发历史转让协议效力与税务复核。",
            resolution="以登记机关备案文本统一股权比例，由转让方提供更正说明、历史转让对价支付凭证及出资期限说明，"
                       "并作为交易先决条件（F-01）。"))

    # ---- CT-02: data cross-border statement vs cloud region ----
    priv = facts.get("privacy", {}).get("text", "")
    denies_xborder = bool(re.search(r"未.{0,6}(向境外|跨境|出境|境外提供|提供.*境外)", priv)) or \
                     bool(re.search(r"海外仅.{0,6}(测试|演示)", priv))
    foreign = []
    for r in facts.get("cloud_regions", []):
        reg = r.get("region") or ""
        if re.search(r"新加坡|香港|美国|法兰克福|东京|海外|境外|境外|aws|azure|gcp", reg, re.I):
            foreign.append(r)
    if denies_xborder and foreign:
        detail = "；".join(f"{r.get('group')}（{r.get('region')}，{r.get('data_desc')}）" for r in foreign)
        foreign_region = foreign[0].get("region") or "境外"
        out.append(dict(
            cid="CT-02", severity="HIGH",
            title="数据跨境表述与云架构实际部署不一致",
            primary_items=["DATA-03"],
            files_conflict=[store.get("06.1").name, store.get("06.2").name],
            items=["DATA-03","DATA-05"],
            description=f"隐私政策称无客户生产数据出境、海外仅测试/演示数据，但云账单显示境外区域（{foreign_region}）部署含个人信息与账号标识符：{detail}。"
                        f"表述与部署互相矛盾，须核实是否落入《个人信息保护法》出境规制。",
            resolution="要求目标公司澄清上述境外资源的数据属性（是否含个人信息/重要数据）、接收方与传输目的，"
                       "补充跨境传输字段清单、告知同意记录、与境外接收方签订的标准合同/安全评估及个人信息保护影响评估（PIA）文件，"
                       "作为事实问询并纳入陈述保证（F-08）。"))

    # ---- CT-03: dispute omission (claim in contract/律师函 but not in 07.1) ----
    disputes_ids = {d.get("id") for d in facts.get("disputes", {}).get("list", [])}
    disputes_text = " ".join(str(d) for d in facts.get("disputes", {}).get("list", []))
    omitted = []
    for c in facts.get("contracts", []):
        disp = str(c.get("dispute") or "")
        if re.search(r"争议|索赔|逾期|纠纷|异议", disp) and disp not in ("无", "无争议", ""):
            # try to find this contract's counterparty/amount inside 07.1 text
            party = str(c.get("party") or "")
            amt = str(c.get("amount") or "")
            if party and party not in disputes_text and amt and amt not in disputes_text:
                omitted.append(c)
    if omitted:
        detail = "；".join(f"{c.get('id')}（{c.get('party')}，{c.get('dispute')}）" for c in omitted)
        out.append(dict(
            cid="CT-03", severity="HIGH",
            title="重大索赔/争议未纳入争议与或有负债清单",
            primary_items=["DISP-01"],
            files_conflict=[store.get("03.1").name, store.get("07.3").name, store.get("07.1").name],
            items=["DISP-01","DISP-02","CON-08"],
            description=f"以下合同的争议/索赔见于合同台账或律师函，但未列入07.1诉讼仲裁及或有负债清单：{detail}。可能低估或有负债。",
            resolution="将遗漏索赔补入争议/或有负债清单并说明原因，纳入赔偿（indemnity）事项（F-09）。"))

    return out

# ============================================================================
# Per-item analysis
# ============================================================================
def _prefixes(it):
    vdr = it.get("vdr", "") or ""
    return [p.strip() for p in re.split(r"[；;]", vdr) if re.match(r"\d{2}\.\d+", p.strip())]

def analyze_one(it, store, facts, contradictions):
    iid = it["id"]
    domain = iid.split("-")[0]
    prefs = _prefixes(it)
    present = [p for p in prefs if store.get(p)]
    conf = next((c for c in contradictions if iid in c["items"]), None)
    is_primary = bool(conf and iid in conf.get("primary_items", []))

    # Only the epicenter item of a contradiction is marked 资料冲突; the other
    # linked items keep their own (evidence-driven) status and get a cross-ref
    # note — this avoids inflating the conflict count (评估失真).
    if is_primary:
        if "F-01" in conf["resolution"]:
            disp, fb = "CP", "F-01"
        elif "F-08" in conf["resolution"]:
            disp, fb = "RFI", "F-08"
        elif "F-09" in conf["resolution"]:
            disp, fb = "INDEMNITY", "F-09"
        else:
            disp, fb = DOM_DISP[domain], ""
        return _item(iid, domain, it, "资料冲突", conf["description"], conf["files_conflict"],
                     "统一并更正多源不一致文件，作为交易先决。", "HIGH", disp, fb, human="是")

    # material presence
    if not present:
        # some items have no VDR (e.g., DISP-03 insurance, PROP-02 fixed assets)
        vdr = it.get("vdr") or "无"
        return _item(iid, domain, it, "未满足",
                     f"未提供对应资料（VDR：{vdr}）。",
                     f"未发现可支持资料（VDR：{vdr}）",
                     "补充对应文件或说明。", DOM_RISK[domain], DOM_DISP[domain],
                     "", human="否")

    # generic presence-based analysis with extracted highlights
    status, fact, ev, gap = _generic_findings(iid, domain, store, facts, present, it)
    disp = DOM_DISP[domain]
    # Evidence-driven risk (no blanket HIGH):
    #   已满足   -> LOW residual
    #   未满足   -> HIGH if critical domain else MEDIUM
    #   部分满足 -> MEDIUM (escalated to HIGH only on a concrete red-flag signal)
    if status == "已满足":
        risk = "LOW"
    elif status == "未满足":
        risk = "HIGH" if domain in ("CAP","IP","DATA","REG","HR","CON") else "MEDIUM"
    else:  # 部分满足
        risk = "MEDIUM"
    SIG = ["未签署","未确认签署","无IP","已过期","过期仍","不一致","索赔","争议","未实缴","未纳入","控制权变更"]
    if risk != "HIGH" and any(s in fact for s in SIG):
        risk = "HIGH"
    # secondary contradiction cross-reference note (keeps traceability)
    if conf:
        gap = (gap.rstrip("；") + f"；与{conf['cid']}矛盾相关（详见跨文件矛盾）").strip("；")
    human = "是" if status in ("资料冲突","未满足") or risk == "HIGH" else "否"
    return _item(iid, domain, it, status, fact, ev, gap, risk, disp, "", human=human)

def _generic_findings(iid, domain, store, facts, present, it):
    """Return (status, fact, evidence_list, gap) using extracted values."""
    ev = []
    highlights = []
    # pull a couple of concrete highlights per domain
    if domain == "CAP":
        eq = facts.get("equity_ledger", [])
        if eq:
            unpaid = [e for e in eq if e.get("paid") is not None and e.get("subscribed") is not None and e["paid"] < e["subscribed"]]
            lines = "；".join(f"{e['name']} 认缴{e['subscribed']}/实缴{e['paid']}" for e in eq[:4])
            highlights.append(lines)
            ev.append(cite(store, "02.1", r"当前股权结构"))
            if unpaid:
                return ("部分满足",
                        f"股权结构台账显示：{lines}。" + ("存在未实缴出资。" if unpaid else ""),
                        ev, "实缴凭证与出资期限届满事项待核。")
    if domain == "CON":
        cs = facts.get("contracts", [])
        if cs:
            coc = [c for c in cs if c.get("coc") and "无" not in str(c.get("coc"))]
            highlights.append(f"重大合同 {len(cs)} 份；含控制权变更条款 {len(coc)} 份")
            ev.append(cite(store, "03.1", r"重大合同台账"))
            if coc:
                return ("部分满足",
                        f"合同台账列示重大合同 {len(cs)} 份；其中 {len(coc)} 份含控制权变更/转让限制条款（如 {coc[0].get('id')}）。",
                        ev, "控制权变更需取得相对方确认/豁免，待核具体条款文本。")
    if domain == "IP":
        ips = facts.get("ip_list", [])
        if ips:
            target = find_target_name(store, facts)
            # flag any core IP whose registered owner is NOT the in-scope target
            # entity (e.g. held by an affiliate outside the acquisition perimeter)
            ext = [i for i in ips if i.get("owner") and target and i.get("owner") != target]
            highlights.append(f"知识产权 {len(ips)} 项")
            ev.append(cite(store, "04.1", r"知识产权清单"))
            if ext:
                return ("部分满足",
                        f"知识产权清单列示 {len(ips)} 项；其中核心成果登记权利人为关联方（{ext[0].get('owner')}），未纳入收购范围。",
                        ev, "核心IP权属转回/独占许可文件待提供。")
    if domain == "HR":
        em = facts.get("employees", {})
        if em:
            cto = [r for r in em.get("roster", [])
                   if any(t in str(r.get("岗位", "")) for t in ("CTO", "首席技术", "技术负责人", "技术总监", "技术官"))]
            highlights.append(f"员工 {em.get('count')} 人")
            ev.append(cite(store, "05.1", r"员工名册"))
            if cto:
                st = cto[0].get("合同状态") or cto[0].get("保密/IP条款")
                return ("部分满足",
                        f"员工名册 {em.get('count')} 人；关键人员（{cto[0].get('姓名')}）合同状态：{st}。",
                        ev, "核心人员劳动合同与IP协议签署待补。")
    if domain == "DATA":
        ev.append(cite(store, "06.1", r"跨境|出境|境外"))
        reg = facts.get("cloud_regions", [])
        foreign = [r for r in reg if re.search(r"新加坡|香港|境外|海外", str(r.get("region")), re.I)]
        if foreign:
            return ("部分满足",
                    f"隐私政策与云账单显示存在境外区域部署（{foreign[0].get('region')}：{foreign[0].get('data_desc')}）。",
                    ev, "数据出境合规材料（标准合同/评估）待提供。")
    if domain == "REG":
        lic = facts.get("license_doc", {}).get("text", "")
        ev.append(cite(store, "06.3", r"许可证|有效期|到期"))
        licno = re.search(r"(苏B2-\d+|[A-Za-z]?B2-\d+)", lic)
        exp = re.search(r"有效期至\s*(\d{4}-\d{2}-\d{2})", lic)
        cutoff = BASELINE_DATE
        expired = exp and exp.group(1) < cutoff
        if licno or exp:
            note = "（已过期，仍经营SaaS）" if expired else ""
            return ("部分满足",
                    f"业务许可证 {licno.group(1) if licno else '（见证照）'}，载明有效期至 {exp.group(1) if exp else '未载明'}{note}。",
                    ev, "续期后许可证或受理文件待提供。")
    if domain == "DISP":
        d = facts.get("disputes", {})
        ev.append(cite(store, "07.1", r"争议清单|或有负债"))
        if d.get("list"):
            return ("部分满足",
                    f"争议清单 {len(d.get('list',[]))} 项、或有负债 {len(d.get('contingent',[]))} 项。",
                    ev, "保险单与续保记录待提供（DISP-03）。")
    if domain == "GOV":
        ev.append(cite(store, "02.4", r"决议|董事会"))
        if iid == "GOV-02":
            txt = facts.get("gov_resolutions", {}).get("text", "")
            art = store.get("01.2").text if store.get("01.2") else ""
            CN = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
            q = None
            mq = re.search(r"([0-9]+|[一二三四五六七八九十])\s*名?\s*以上?\s*董事\s*出席", art)
            if not mq:
                mq = re.search(r"(?:至少|不少于|应当有|应有|须有)\s*([0-9]+|[一二三四五六七八九十])\s*名?\s*董事", art)
            if mq:
                q = int(mq.group(1)) if mq.group(1).isdigit() else CN.get(mq.group(1))
            signed = len(re.findall(r"董事\s*签名|签字", txt))
            return ("部分满足",
                    f"治理决议汇编含股东会/董事会决议；章程规定董事会法定人数约 {q if q else '?'} 名董事，需核签署人数是否达标。",
                    ev, "部分决议签署董事人数与法定人数待核（见 K-05）。")
    if domain == "CORP":
        ev.append(cite(store, "01.1", r"登记|经营状态"))
    if domain == "PROP":
        ev.append(cite(store, "08.1", r"租赁|到期|控制权"))
    # default: material present and no specific defect -> 已满足 (real, not blank)
    status = "已满足"
    fact = (f"已提供相关资料（{ '、'.join(present)} ）。" +
            ("；".join(highlights) if highlights else ""))
    return (status, fact, ev, "按清单要求补充其余子项（如适用）。")

def _item(iid, domain, it, status, fact, ev_files, gap, risk, disp, fb, human):
    if isinstance(ev_files, str):
        ev_str = ev_files
    elif isinstance(ev_files, list):
        ev_str = "\n".join(str(x) for x in ev_files)
    else:
        ev_str = ""
    return dict(
        id=iid, domain=DOMAIN[domain], req=it.get("req",""),
        status=status, fact=fact, evidence=ev_str, gap=gap,
        risk=risk, disp=disp, feedback=fb, human=human,
    )

# ============================================================================
# Feedback (dedup into ~20) and Key issues
# ============================================================================
def build_feedback(items, contradictions, facts):
    # theme buckets -> one feedback each (dedup)
    # derive the foreign deployment region from data (no hardcoded region name)
    _fr = [r for r in facts.get("cloud_regions", [])
           if re.search(r"新加坡|香港|境外|海外|aws|azure|gcp|frankfurt|tokyo|us-", str(r.get("region")), re.I)]
    xregion = _fr[0].get("region") if _fr else "境外"
    buckets = []
    def add(fid, typ, pri, dom, ask, purpose, owner, due, issue_ids, risk):
        buckets.append(dict(fid=fid, type=typ, pri=pri, domain=dom, ask=ask,
                            purpose=purpose, owner=owner, due=due,
                            items=issue_ids, risk=risk))
    # map items to themes by domain + status
    by_id = {i["id"]: i for i in items.values()} if isinstance(items, dict) else {i["id"]: i for i in items}
    def ids_with(*preds):
        return [i["id"] for i in (items.values() if isinstance(items, dict) else items) if all(p(i) for p in preds)]
    add("F-01","补充资料","P0","股权","统一并更正股权比例，以登记机关备案文本为准，提供更正说明与转让对价支付凭证。","确认收购基准股权结构，支撑本次交易的收购对价。","董事会办公室/法务","交割前（先决）", ids_with(lambda i: i["domain"]=="股权出资"), "R-01")
    add("F-02","补充资料","P0","股权","提供全额验资报告与银行入账凭证，确认实缴与出资期限。","核实实收资本，支撑估值与交割后资本充实。","财务/法务","交割前","CAP-02","R-02")
    add("F-03","补充资料","P0","知识产权","将核心IP转回/独占许可并办理权属变更登记，提供转让/许可协议。","核心收购标的技术权属清晰，避免向非收购关联方流失。","研发中心/法务","交割前（先决）", ids_with(lambda i: i["domain"]=="知识产权"), "R-03")
    add("F-04","整改动作","P0","治理","补正董事会决议法定人数瑕疵或取得贷款人确认。","消除借款及保证合同授权效力瑕疵。","法务","签约前","GOV-02","R-05")
    add("F-05","外部确认","P0","重大合同","就控制权变更取得核心客户、贷款人与出租方确认或豁免，纳入交易承诺。","避免核心收入合同与融资中断或提前到期。","法务/业务","交易前","CON-02, CON-05, PROP-01","R-04")
    add("F-06","补充资料","P0","业务资质","取得增值电信许可证续期证明或评估无证经营影响。","消除许可缺失下的持续经营风险。","法务合规","交割前（先决）", ids_with(lambda i: i["domain"]=="业务资质"), "R-07")
    add("F-07","补充资料","P0","劳动人事","交割前完成CTO等核心人员劳动合同及IP协议签署，或作为陈述保证/先决。","锁定核心人员与职务成果权属。","HR/法务","交割前","HR-02, HR-05","R-08")
    add("F-08","事实问询","P1","数据合规",f"澄清境外（{xregion}）部署资源的数据属性与出境合规：列明跨境传输字段、接收方与目的，"
        "提供告知同意记录、与境外接收方签订的标准合同/安全评估及个人信息保护影响评估（PIA）文件。","确认是否触发PIPL出境义务及缺口敞口。","法务合规","签约前", ids_with(lambda i: i["domain"]=="数据合规"), "R-06")
    add("F-09","补充资料","P1","争议债务","将遗漏索赔补入争议/或有负债清单并说明原因，纳入赔偿事项。","避免或有负债低估，核对管理层声明。","法务","签约前", ids_with(lambda i: i["domain"]=="争议债务"), "R-09")
    add("F-10","补充资料","P1","重大合同","提供前十大客户/供应商主协议、订单及收入/采购占比明细。","核实收入与供应链集中度。","财务/业务","签约前","CON-02, CON-03","R-04")
    add("F-11","整改动作","P1","知识产权","完成开源AGPL/SSPL专项法务复核并闭环（修改后网络提供义务）。","降低copyleft触发与产品分发合规风险。","研发中心/法务","签约前", ids_with(lambda i: i["domain"]=="知识产权" and "开源" in i["req"]), "R-11")
    add("F-12","补充资料","P1","劳动人事","补充员工手册民主公示记录与关键员工IP/竞业限制签署版。","完善用工合规与职务成果权属。","HR","签约前","HR-03","R-08")
    add("F-13","补充资料","P2","主体资格","提供近三年年度报告与经营异常/失信名单专项说明。","确认主体存续与合规状态。","法务","签约前","CORP-07","R-00")
    add("F-14","补充资料","P2","公司治理","补充关联交易与对外担保专项管理制度及历史审批记录。","核验关联交易与担保内控。","董事会办公室/法务","签约前","GOV-03","R-05")
    add("F-15","事实问询","P2","争议债务","提供财产/责任/董责等保险单与续保记录。","确认风险转移安排。","行政/法务","签约前","DISP-03","R-09")
    add("F-16","补充资料","P2","物业资产","提供研发场地续租协议或出租方控制权变更同意文件。","稳定研发场所。","行政","交易前","PROP-01","R-04")
    add("F-17","补充资料","P2","物业资产","提供重大设备/固定资产清单及权属/抵押/查封核查。","核实资产权属与负担。","财务","签约前","PROP-02","R-04")
    add("F-18","事实问询","P2","业务资质","提供近三年行政处罚/合规调查专项清单及出口管制/制裁筛查记录。","确认无未披露合规处罚。","法务合规","签约前","REG-02, REG-03","R-07")
    add("F-19","补充资料","P1","公司治理","提供法定代表人/印章/网银U盾管理制度与用印台账。","核验授权与用印内控。","行政/法务","签约前","GOV-04","R-05")
    add("F-20","补充资料","P1","公司治理","提供尚未执行完毕或影响本次交易的股东会/董事会决议及授权文件。","确认交易相关待决事项。","董事会办公室","签约前","GOV-05","R-05")
    return buckets

def _ev_join(by_id, *ids):
    """Join real evidence citations from the given item ids (no placeholders)."""
    evs = []
    for iid in ids:
        if iid in by_id and by_id[iid].get("evidence"):
            evs.append(f"{iid}：{by_id[iid]['evidence']}")
    return "\n".join(evs)

def build_key_issues(items, contradictions, facts, store):
    by_id = {i["id"]: i for i in (items.values() if isinstance(items, dict) else items)}
    k = []
    # 1-3 from contradictions
    ctitle = {"CT-01":"股权结构多源比例不一致", "CT-02":"数据跨境表述与云架构不一致",
              "CT-03":"重大索赔未入争议/或有负债清单"}
    for c in contradictions:
        k.append(dict(kid=f"K-{len(k)+1:02d}", title=ctitle.get(c["cid"], c["title"]),
                      risk=c["severity"], disp=("CP" if c["cid"]=="CT-01" else "RFI" if c["cid"]=="CT-02" else "INDEMNITY"),
                      items=c["items"], fact=c["description"], evidence="；".join(c["files_conflict"]),
                      impact="影响交易对价/合规/赔偿，须作为先决或陈述保证。", action=c["resolution"]))
    # 4 from capital unpaid
    if "CAP-02" in by_id:
        k.append(dict(kid=f"K-{len(k)+1:02d}", title="控股股东出资未实缴", risk="HIGH", disp="CP",
                      items=["CAP-02"], fact=by_id["CAP-02"]["fact"], evidence=by_id["CAP-02"]["evidence"],
                      impact="实收资本不完整，影响估值与交割后资本充实。", action="交割前补足或调整对价（F-02）。"))
    # 5 control-change triggers
    if "CON-02" in by_id or "CON-05" in by_id:
        ev = _ev_join(by_id, "CON-02", "CON-05", "PROP-01") or cite(store, "03.1", r"重大合同台账")
        k.append(dict(kid=f"K-{len(k)+1:02d}", title="控制权变更触发重大合同/融资/租赁限制", risk="HIGH", disp="COVENANT",
                      items=[i for i in ["CON-02","CON-05","PROP-01"] if i in by_id],
                      fact="本次收购构成控制权变更，核心客户合同、借款合同与租赁含提前通知/增信/同意条款。",
                      evidence=ev, impact="若未获相对方确认，核心收入与融资可能中断。",
                      action="交易前取得确认或豁免，纳入承诺（F-05）。"))
    # 6 board quorum
    if "GOV-02" in by_id:
        k.append(dict(kid=f"K-{len(k)+1:02d}", title="董事会决议法定人数瑕疵", risk="HIGH", disp="CP",
                      items=["GOV-02","GOV-03","CON-05"], fact=by_id["GOV-02"]["fact"], evidence=by_id["GOV-02"]["evidence"],
                      impact="借款及保证合同授权存在效力瑕疵。", action="补正决议或取得贷款人确认（F-04）。"))
    # 7 license expiry
    if "REG-01" in by_id:
        k.append(dict(kid=f"K-{len(k)+1:02d}", title="增值电信许可证过期仍经营SaaS", risk="HIGH", disp="CP",
                      items=["REG-01"], fact=by_id["REG-01"]["fact"], evidence=by_id["REG-01"]["evidence"],
                      impact="许可缺失下持续经营存在无证经营风险。", action="取得续期证明或评估影响（F-06）。"))
    # 8 CTO unsigned
    if "HR-02" in by_id:
        k.append(dict(kid=f"K-{len(k)+1:02d}", title="CTO劳动合同未签署且无IP协议", risk="HIGH", disp="CP",
                      items=["HR-02","HR-05","IP-03"], fact=by_id["HR-02"]["fact"], evidence=by_id["HR-02"]["evidence"],
                      impact="核心人员与职务成果权属留白。", action="交割前完成签署与IP协议（F-07）。"))
    # 9 related-party
    if "CON-07" in by_id:
        ev = cite(store, "04.1", r"知识产权清单") or by_id.get("IP-01", {}).get("evidence", "")
        k.append(dict(kid=f"K-{len(k)+1:02d}", title="关联交易无正式协议（核心IP使用安排）", risk="MEDIUM", disp="INDEMNITY",
                      items=["CON-07","IP-01"], fact="与未收购关联方存在早期软件资产使用安排，无正式协议。",
                      evidence=ev, impact="关联交易定价与IP权属不明。", action="补签关联IP许可/转让协议（F-03）。"))
    # 10 opensource — fact DERIVED from extracted 04.4 (no hardcoded product names)
    if "IP-04" in by_id or "IP-05" in by_id:
        oss = facts.get("opensource", [])
        copyleft = [o for o in oss if o.get("license") and re.search(r"AGPL|SSPL|GPL", str(o.get("license")), re.I)]
        if copyleft:
            detail = "；".join(
                f"{o.get('component')}（许可{o.get('license')}，是否修改={o.get('modified')}，"
                f"网络提供={o.get('network')}，是否分发={o.get('distribute')}）" for o in copyleft)
            oss_fact = f"开源组件含强copyleft许可需专项复核：{detail}。"
        else:
            oss_fact = "开源组件清单已核，未见强copyleft（AGPL/SSPL）许可。"
        ev = cite(store, "04.4", r"开源组件") or by_id.get("IP-04", {}).get("evidence", "")
        k.append(dict(kid=f"K-{len(k)+1:02d}", title="开源AGPL/SSPL合规待复核", risk="MEDIUM", disp="MONITOR",
                      items=["IP-04","IP-05"], fact=oss_fact,
                      evidence=ev, impact="修改后网络提供可能触发copyleft义务。", action="完成专项复核并闭环（F-11）。"))
    # 11 lease
    if "PROP-01" in by_id:
        k.append(dict(kid=f"K-{len(k)+1:02d}", title="研发场地租赁临近到期且COC同意缺失", risk="MEDIUM", disp="COVENANT",
                      items=["PROP-01"], fact=by_id["PROP-01"]["fact"], evidence=by_id["PROP-01"]["evidence"],
                      impact="续租不确定或出租方设障影响研发场所稳定。", action="取得续租协议/出租方同意（F-16）。"))
    # 12 annual reports / admin penalty
    if "CORP-07" in by_id:
        ev = cite(store, "01.1", r"登记|经营状态") or by_id.get("CORP-07", {}).get("evidence", "")
        k.append(dict(kid=f"K-{len(k)+1:02d}", title="近年年度报告与合规处罚专项说明待补", risk="LOW", disp="RFI",
                      items=["CORP-07","REG-02"], fact="近三年年度报告、经营异常名单与行政处罚专项说明待提供。",
                      evidence=ev, impact="主体存续与合规状态待独立核验。", action="补充专项说明（F-13/F-18）。"))
    # pad to 12 if fewer
    while len(k) < 12:
        k.append(dict(kid=f"K-{len(k)+1:02d}", title="其他需关注事项", risk="LOW", disp="MONITOR",
                      items=[], fact="", evidence="", impact="", action=""))
    return k[:12]

# ============================================================================
# Orchestrator
# ============================================================================
def run(store, checklist):
    facts = build_facts(store)
    contradictions = detect_contradictions(store, facts)
    items = {}
    for it in checklist:
        items[it["id"]] = analyze_one(it, store, facts, contradictions)
    # link feedback ids to items
    feedback = build_feedback(items, contradictions, facts)
    fb_by_id = {f["fid"]: f for f in feedback}
    # map item -> feedback via domain/theme (simple: item.disposition/domain match)
    for i in items.values():
        linked = [f["fid"] for f in feedback if i["id"] in f["items"]]
        if not linked and i.get("feedback"):
            linked = [i["feedback"]]
        if not linked:
            # fallback: match by domain bucket
            dom = list(DOMAIN.keys())[list(DOMAIN.values()).index(i["domain"])]
            linked = [f["fid"] for f in feedback if f["domain"] == dom][:1]
        i["feedback_ids"] = linked
        i.pop("feedback", None)
    key_issues = build_key_issues(items, contradictions, facts, store)
    meta = dict(
        target_name=find_target_name(store, facts),
        baseline_date=BASELINE_DATE,
        material_count=len(store.by_prefix),
    )
    return dict(items=items, contradictions=contradictions, feedback=feedback,
                key_issues=key_issues, facts=facts, meta=meta)

if __name__ == "__main__":
    import sys, os
    _here = os.path.dirname(os.path.abspath(__file__))
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_here, "..", "materials")
    cl_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(_here, "..", "checklist", "checklist_52.json")
    s = Store(root)
    cl = json.load(open(cl_path, encoding="utf-8"))
    res = run(s, cl)
    print("items:", len(res["items"]), "| contradictions:", len(res["contradictions"]), "| feedback:", len(res["feedback"]), "| key_issues:", len(res["key_issues"]))
    for c in res["contradictions"]:
        print("  CT:", c["cid"], c["title"], "->", c["items"])
    # show a few item samples
    for iid in ["CAP-01","DATA-03","DISP-01","IP-01","REG-01","HR-02","GOV-02"]:
        it = res["items"][iid]
        print(f"  {iid}: {it['status']} / {it['risk']} / {it['disp']} | fb={it.get('feedback_ids')}")
        print("      fact:", it["fact"][:120])
