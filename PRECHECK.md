# PRECHECK — legal-dd-verify 方案包自检

本文件用于加载方案包前快速核验其完整性与质量护栏。

## 1. 必交包文件

| 文件 | 存在 | 说明 |
|---|---|---|
| `.codebuddy-plugin/plugin.json` | ✅ | 插件清单，声明入口 `agents/main-agent.md` 与模型约束 |
| `agents/main-agent.md` | ✅ | 主代理入口（entrypoint），定义执行流程与硬性约束 |
| `README.md` | ✅ | 方案说明 + 用途边界 |
| `PRECHECK.md` | ✅ | 本文件 |

## 2. 运行环境

- Python >= 3.8（WorkBuddy 内置运行时）
- 第三方库（已 vendored，无网络/无外部模型）：
  - `pypdf`（解析 PDF，位于 `vendor/`）
  - `openpyxl`（读写 XLSX，位于 `vendor/`）
  - `.docx` 由自研纯标准库 `_docx.py` 解析（替代 `python-docx`，规避 `lxml` C 扩展）
- 依赖随包离线打包，运行期无需 `pip install`、无需联网。

## 3. 运行命令

```bash
python3 pipeline/run.py --input materials --checklist checklist/checklist_52.json --out examples --verify
```

## 4. 质量护栏自检

| 护栏 | 本包状态 |
|---|---|
| 四项必交成果缺失两项及以上 / 主文件损坏 | ✅ 4 件均由脚本生成且可被 openpyxl / 自研 docx 解析器 / json 正常打开 |
| 大量虚构输入中不存在的文件、审批、登记等 | ✅ 所有证据定位由 `extract.py` 从真实源文件抽取；`verify.py` 逐条比对源文件，0 未解析引用 |
| 把"未提供"系统性表述为已违法/无效 | ✅ 状态字段区分"资料缺失"与"已证实风险"，缺口写入"资料缺口/待提供" |
| 调用内置模型以外的模型 / 外部服务 | ✅ 仅用运行环境内置模型；流水线为纯 Python，零网络调用 |
| 使用禁止外部服务 / 将资料或成果送出运行目录 | ✅ 不写文件出运行目录；无外部请求 |
| **硬编码实例答案 / 捆绑预生成交付物** | ✅ **方案包内不含任何写死的成品**；交付物运行期生成；源码零实例专有答案 |

## 5. 核心成果门槛自检

- ✅ 四项必交成果齐全可解析
- ✅ 52 个清单项全部覆盖且编号唯一（`verify.py` 断言）
- ✅ 不引用不存在的文件/工作表/单元格/条款（`verify.py` 断言）
- ✅ 股权/出资、核心知识产权、数据跨境、控制权变更四类核心风险强制覆盖（`verify.py` 断言）
- ✅ 重点问题 ↔ 核验总表 ↔ 补件清单三层互链、编号唯一
- ✅ 区分"资料缺失"与"已证实风险"

> 注：本包**不捆绑** `deliverables/`。交付物由 `agents/main-agent.md` 在运行期调用 `pipeline/run.py` 生成，确保指向不同资料室时无需修改方案包、且不预置成品。
