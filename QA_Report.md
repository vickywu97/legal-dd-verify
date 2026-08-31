# QA Report — legal-dd-verify（尽职调查资料核验流水线）

**Subject**: legal-dd-verify due-diligence verification pipeline
**Nature**: deterministic rule + cross-file contradiction-detection engine (not a statistical / ML model)
**Scope of this report**: offline runnability, output consistency, and the independent verifier's guarantees on the bundled original demo data room.

---

## 1. Test environment

- Python 3.8+ (no third-party `pip` install at runtime; deps vendored).
- Clean-container check: run with `python3 -S` (no user site-packages) and `PYTHONPATH=vendor` only → pipeline + verifier execute end-to-end.
- Source scan (excluding `vendor/`): 0 literals tied to the demo's proper nouns (names/addresses/account IDs are all synthetic and live only in `materials/`); no hardcoded "answers" outside `profile.py` transaction-frame constants.

---

## 2. What the independent verifier guarantees

`pipeline/verify.py` does **not** import the analysis engine. It reads the 4 deliverables + the authoritative source files and asserts:

| Check | Expected | Result (demo) |
| --- | --- | --- |
| manifest items == 52, unique | pass | pass |
| key_issues count in 8–12 | pass | 12 |
| ≥ 1 cross-file contradiction recorded | pass | 3 |
| citations resolve to real source files | 0 unresolved | manifest 0 / xlsx 0 |
| status / risk enums valid | pass | pass |
| 4 core risks covered (股权/出资 · 核心知识产权 · 数据跨境 · 控制权变更) | pass | all 4 |
| 核验总表 == 52 rows; disp enum valid | pass | pass |
| 补件问询 15–22 条且类型合法 | pass | 20 |
| docx 含规定章节 + ≥8 个 K- 重点问题 | pass | 7 sections / 12 K- |

**Verdict: PASS.**

---

## 3. Findings

| # | Finding | Severity | Type | Status |
| --- | --- | --- | --- | --- |
| 1 | `extract.py` 的文档前缀抽取原为 `^(\d{2}\.\d+)`（锚定文件名开头），而实际/演示文件名以"类别__XX.Y_"开头，导致前缀匹配失败、`store.get("XX.Y")` 返回空、事实抽取全空、矛盾数为 0。已改为 `re.search(r"(\d{2}\.\d+)", base)`。 | High | Bug (fixed) | Fixed |
| 2 | 事实抽取层 `build_facts` 使用精确表名查找（`.get(name, [])`）；若资料室使用不同表名，抽取会优雅降级（不崩溃）但事实变空。 | Low | Robustness / Feature | Documented (see scope boundary) |
| 3 | 矛盾"震中"项标记"资料冲突"，其余关联项仅做交叉引用，避免矛盾计数虚高。 | Info | Design | OK |
| 4 | 全部结论由 `extract → analyze → render` 实时推导；唯一常量是交易框架（`profile.py`），属方案设计参数，非实例答案。 | Info | Design | OK |

---

## 4. Known limitations

- 流水线绑定演示数据室的文档结构；用于文档结构不同的真实项目需扩展 `build_facts` 与矛盾检测规则。
- 校验器校验"交付物与源文件的一致性 + 结构完整性"，不校验法律结论的实体正确性——后者仍需承办律师复核（交付物已标注"需人工复核"项与范围限制）。
- 演示数据室为虚构合成信息，不映射任何真实事件；运行结果中的"范围限制"章节已注明。

---

## 5. Reproduce

```bash
cd pipeline
python3 run.py --out ../examples --verify
# 末行应输出：RESULT: PASS — citations resolve, 52/unique, enums valid,
#           core risks covered, contradictions recorded, sections present.
```
