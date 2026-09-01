# legal-dd-verify — Release Notes

## v1.1.0 (multi-scenario demo data rooms)

- **多场景可切换演示数据室**：新增 `scenarios/` 注册机制与 `run.py --scenario <key|path>`。仓库内置两个**完全独立、无共享专有名词**的原创合成数据室——`cloudlink`（默认，霁川智链 SaaS）与 `hanwei_semi`（琢微半导体，半导体 / AI 芯片）。二者植入不同的三类结构性问题（股权比例冲突、数据跨境表述 vs 云架构、供应商索赔漏列），同一引擎分别重新推导全部结论，均通过独立校验器（52 项 / 12 重点问题 / 3 矛盾 / 4 核心风险 / 0 未解析引注）。
- `pipeline/scenario.py`：场景注册表 + `Scenario` 对象（资料目录 / 清单 / 交易框架常量 / 元数据）。默认 `cloudlink` 向后兼容（仍指向仓库根 `materials/` + `checklist/` + `pipeline/profile.py`）。
- `analyze.py` / `render.py` 改为按场景注入 `baseline_date` 与交易框架（买方 / 受让比例），不再依赖全局常量；默认输出与 v1.0.0 字节一致。
- `tests/smoke_test.py` 扩展为对**每个**内置场景跑通整链并断言 `RESULT: PASS`。
- `scenarios/hanwei_semi/gen.py` 可复现该数据室，证明其为合成来源。

## v1.0.0 (initial release)

首个公开版本：一个**数据驱动**的法律尽职调查资料核验流水线，绑定一份**完全原创、合成**的演示数据室（"霁川智链科技股份有限公司"，29 份资料），端到端可复现。

### 包含内容
- `pipeline/`：抽取 → 分析（52 项核验 + 跨文件矛盾检测）→ 渲染（4 件交付物）→ 独立校验 四层引擎。
- `materials/`：原创合成演示数据室（离线 `.txt` 抽取视图，零二进制依赖）。
- `checklist/checklist_52.json`：通用 52 项核查清单（保留编号与资料指向结构，措辞为原创重述）。
- `examples/`：绑定演示数据室的运行结果（已通过独立校验器，RESULT: PASS）。
- `evaluation/`：独立校验器入口与说明。
- `vendor/`：离线 vendored 依赖（pypdf / openpyxl / et_xmlfile）；`_docx.py` 纯标准库 `.docx` 读写。
- `agents/`、`SKILL.md`、`prompts.md`、`mcp.md`、`PRECHECK.md`：主代理说明与离线运行约束。

### 设计要点
- **数据驱动，不写死答案**：目标公司名、关联方、境外区域、年份、关键人、股权比例等全部运行期抽取；唯一常量为 `profile.py` 交易框架（买方/受让比例/基准日）。
- **离线 / 零依赖安装**：运行期无需 `pip`、无需联网；`.docx` 由自研 `_docx.py` 替代 `python-docx`（规避 `lxml` C 扩展）。
- **独立校验器**：不依赖分析引擎，反向解析引用、校验枚举与核心风险覆盖。

### 修复记录
- 修复 `extract.py` 文档前缀抽取锚定开头导致 `XX.Y` 匹配失败、事实全空、矛盾数为 0 的缺陷（改为 `re.search`）。

### 诚实边界
- 本仓库为方法论可运行示例，绑定原创合成演示数据室；演示数据室与任何真实主体/项目/第三方题库无关。
- 输出为律师支持性分析，非独立法律意见，不替代对登记机关、主管机关及相对方的独立核验。
- 引擎绑定演示数据室文档结构；用于不同文档结构的真实项目需扩展事实抽取与矛盾检测规则。

### License
MIT
