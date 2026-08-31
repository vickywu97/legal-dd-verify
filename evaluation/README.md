# 评测 / 独立校验材料（Evaluation & Independent Verification）

本目录包含对交付物的**独立一致性校验器** `verify.py`，用于在提交前或运行后
复验成果是否满足基本质量门槛。**它不是竞赛评分器**，而是一把可复现的"自检尺"：
只读取交付物与源文件，不依赖分析引擎，因此可以从第三方的角度独立核查。

## 一、校验器做了什么

`verify.py`（实际逻辑在 `pipeline/verify.py`，本目录的 `verify.py` 是其薄入口）检查：

| 检查项 | 期望 |
| --- | --- |
| manifest 的 items == 52，且编号唯一 | pass |
| key_issues 数量在 8–12 | pass |
| 至少记录 1 处跨文件矛盾 | pass |
| 引用能解析到真实源文件（无编造） | 0 未解析 |
| status / risk 枚举合法 | pass |
| 四类核心风险（股权/出资 · 核心知识产权 · 数据跨境 · 控制权变更）覆盖 | 全覆盖 |
| 核验总表 == 52 行；处置类型枚举合法 | pass |
| 补件问询 15–22 条且类型合法 | pass |
| 重点问题摘要含规定章节 + ≥8 个 `K-` 重点问题 | pass |

任一检查不通过即判 `RESULT: FAIL` 并列出具体错误；全部通过则 `RESULT: PASS`。

## 二、如何运行

```bash
# 校验绑定演示数据室的运行结果（examples/）
python3 evaluation/verify.py

# 或显式指定输出与资料室
python3 evaluation/verify.py --out examples --input materials
```

也可直接调用引擎内部的校验器：

```bash
python3 pipeline/run.py --out examples --verify
```

## 三、设计要点（质量护栏，而非竞赛评分）

- **引用不可编造**：每条证据精确到源文件名，校验器反向解析，落到真实源文件才算通过。
- **核心风险不得漏评**：四类强制覆盖，由校验器断言。
- **矛盾必须记录并挂接**：跨文件矛盾结构化记录，且关联清单项均存在。
- **枚举收敛**：状态/风险/处置均限定为既定枚举，避免自由文本漂移。

## 四、运行 smoke test

`tests/smoke_test.py` 会端到端运行整条流水线（抽取→分析→渲染→校验）于绑定演示数据室，
并断言校验结果为 `RESULT: PASS`：

```bash
python3 tests/smoke_test.py
```
