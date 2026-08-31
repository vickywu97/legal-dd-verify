# MCP / 工具面说明

## 一、本方案的工具依赖

本方案是**自包含**的本地 Python 流水线，运行期仅依赖两项纯 Python 库（已 vendored），
无需任何外部 MCP 服务即可完成全部交付：

| 工具 | 用途 | 说明 |
|---|---|---|
| `pypdf` | 抽取 PDF 文本与表格 | vendored 于 `vendor/`，无需安装 |
| `openpyxl` | 读写 XLSX（含统计公式） | vendored 于 `vendor/`，无需安装 |
| `_docx.py` | 生成 / 读取 .docx | 自研纯标准库实现，替代 `python-docx`（规避 `lxml` C 扩展） |

> 全部依赖随包离线打包，运行期无需 `pip install`、无需联网，适配受限/沙箱运行环境。

## 二、可选 MCP：filesystem（如需在 MCP 环境中运行）

若运行环境要求通过 MCP 暴露文件读写能力，可挂载一个只读 filesystem MCP，
将 `materials/` 与 `pipeline/` 目录授权给模型。示例配置：

```json
{
  "mcpServers": {
    "legal-dd-verify-files": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem",
               "/path/to/materials",
               "/path/to/pipeline"],
      "env": {}
    }
  }
}
```

本方案的 `extract.py` 已通过标准文件系统 API 读取资料，**不强制依赖 MCP**；
上述配置仅为在 MCP 托管环境下提供等价能力。

## 三、方案内部"工具面"（模块职责）

| 模块 | 输入 | 输出 | 类比 MCP 工具 |
|---|---|---|---|
| `extract.py` | 资料目录 | `MaterialStore` + 结构化事实 | `read_materials` |
| `analyze.py` | `MaterialStore` + 清单 | 52 项 + 矛盾 + 补件 + 重点问题 | `verify_checklist` |
| `render.py` | 分析结果 | 4 件交付物 | `render_deliverables` |
| `verify.py` | 交付物 + 源文件 | PASS/FAIL + 核心风险覆盖 | `consistency_check` |
| `run.py` | 命令行参数 | 串联以上并落盘 | `orchestrate` |

## 四、无外部网络调用

方案全程离线运行，**不调用任何外部 API、不上传资料、不进行联网检索**，
满足数据不出域的要求（演示数据为虚构合成信息）。
