#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scenario registry for legal-dd-verify.

The pipeline engine is schema-driven: a "scenario" is a self-contained bundle of
  - a data room (materials/) conforming to the demo document schema,
  - a 52-item checklist (checklist.json),
  - engagement-frame constants (profile.json: acquirer / deal_pct / baseline_date),
  - metadata (scenario.json: display_name / sector / blurb).

The built-in scenario `cloudlink` maps to the repo-root `materials/` + `checklist/`
+ `pipeline/profile.py` (the originally shipped demo), so the default behaviour is
fully backward compatible. Additional scenarios live under `scenarios/<key>/` and
are selected with `run.py --scenario <key|path>`.

No scenario-specific "answer" is ever hardcoded in the engine — only the
transaction frame (buyer / stake / as-of date) is a per-scenario constant, which is
by design (it is not an extracted fact).
"""
import os, json, sys, importlib.util

_SUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = _SUB


def _load_profile_py(path):
    """Load pipeline/profile.py constants by path (no sys.path dependency)."""
    spec = importlib.util.spec_from_file_location("profile", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {
        "acquirer": getattr(mod, "ACQUIRER", ""),
        "deal_pct": getattr(mod, "DEAL_PCT", 0),
        "baseline_date": getattr(mod, "BASELINE_DATE", "2026-07-15"),
    }


# ---- built-in scenarios (default behaviour is repo-root compatible) ---------
BUILTINS = {
    "cloudlink": {
        "display_name": "霁川智链科技股份有限公司（企业 SaaS / 数据合规）",
        "sector": "企业 SaaS / 数据合规",
        "blurb": "原版演示数据室：虚构 SaaS 公司的第一轮资料，植入股权比例冲突、数据跨境表述与云架构矛盾、供应商索赔漏列三类结构性问题。",
        "materials_dir": os.path.join(ROOT, "materials"),
        "checklist_path": os.path.join(ROOT, "checklist", "checklist_52.json"),
        "profile": _load_profile_py(os.path.join(ROOT, "pipeline", "profile.py")),
        "meta": {},
    },
}


class Scenario:
    def __init__(self, key, display_name, materials_dir, checklist_path,
                 profile, meta=None):
        self.key = key
        self.display_name = display_name
        self.materials_dir = materials_dir
        self.checklist_path = checklist_path
        self.profile = profile or {}
        self.meta = meta or {}

    @property
    def acquirer(self):
        return self.profile.get("acquirer", "")

    @property
    def deal_pct(self):
        return self.profile.get("deal_pct", 0)

    @property
    def baseline_date(self):
        return self.profile.get("baseline_date", "2026-07-15")

    def __repr__(self):
        return f"Scenario({self.key}: {self.display_name})"


def load(key_or_path=None):
    """Resolve a Scenario from a built-in key or a scenario directory path.

    - None / "cloudlink"  -> the built-in repo-root demo (backward compatible)
    - an existing directory -> a scenario bundle under that dir
                             (must contain materials/ + profile.json)
    - any other key        -> falls back to cloudlink
    """
    if not key_or_path:
        key_or_path = "cloudlink"

    if os.path.isdir(key_or_path):
        sd = key_or_path
        pj = os.path.join(sd, "profile.json")
        prof = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else {}
        cj = os.path.join(sd, "checklist.json")
        if not os.path.exists(cj):
            cj = os.path.join(sd, "checklist_52.json")
        sj = os.path.join(sd, "scenario.json")
        meta = json.load(open(sj, encoding="utf-8")) if os.path.exists(sj) else {}
        disp = meta.get("display_name") or os.path.basename(os.path.normpath(sd))
        return Scenario(os.path.basename(os.path.normpath(sd)), disp,
                        os.path.join(sd, "materials"), cj, prof, meta)

    spec = BUILTINS.get(key_or_path, BUILTINS["cloudlink"])
    key = key_or_path if key_or_path in BUILTINS else "cloudlink"
    return Scenario(
        key, spec["display_name"], spec["materials_dir"], spec["checklist_path"],
        spec["profile"], {**spec.get("meta", {}), "sector": spec.get("sector", ""),
                          "blurb": spec.get("blurb", "")},
    )


def list_builtins():
    return list(BUILTINS.keys())
