# AITestCraft

基于 AI 的智能测试用例生成系统，支持多源需求输入（PDF / 飞书 / 语雀 / TAPD / 石墨 / Confluence），通过 7 节点工作流自动生成高质量测试用例，输出 JSON / Markdown / XMind 多格式文档。

---

## 项目结构

```
AITestCraft/
├── agents/                # Agent 构建
│   ├── base.py            # Agent 工厂与客户端单例
│   └── prompts.py         # Prompt 模板
├── api/                   # API 层
│   ├── endpoints/
│   │   └── tasks.py       # 任务接口（提交/状态/结果/日志）
│   ├── services/
│   │   ├── task_service.py       # 任务执行与重试逻辑
│   │   └── content_resolver.py   # 多源内容解析入口
│   ├── schemas.py         # 数据模型
│   └── main.py            # FastAPI 应用
├── config/
│   └── config.py          # 配置类（环境变量驱动）
├── core/                  # 工作流引擎
│   ├── workflow.py        # 工作流编排 + 断点恢复
│   ├── node.py            # 节点执行（Token 采集 + 双格式输出）
│   ├── context.py         # 上下文 + TokenStats（持久化恢复）
│   ├── taskexecution.py   # 任务执行入口
│   ├── retry.py           # 重试策略
│   ├── schemas.py         # JSON Schema 校验
│   └── workflow_builders.py  # 工作流构建
├── skills/                # AI 技能模块
│   ├── requirement-parser/      # 需求解析
│   ├── testpoint-extractor/     # 测试点提取
│   ├── testpoint-deduplicator/  # 测试点去重
│   ├── testcase-generator/      # 测试用例生成
│   ├── testcase-reviewer/       # 用例审查
│   ├── testcase-coverage/       # 覆盖率分析
│   └── gap-filler/              # 缺口填充
├── storage/
│   ├── db.py              # SQLite 连接池 + Schema
│   └── repositories.py    # 数据访问层
├── utils/
│   ├── parsers/           # 文档平台解析器
│   │   ├── __init__.py    # 注册表（按域名匹配）
│   │   ├── feishu.py      # 飞书（文档/知识库/多维表格）
│   │   ├── yuque.py       # 语雀
│   │   ├── tapd.py        # TAPD
│   │   ├── shimo.py       # 石墨
│   │   └── confluence.py  # Confluence
│   ├── pdf_parser.py      # PDF 解析（文本 + OCR 双通道）
│   ├── md_parser.py       # Markdown 解析
│   ├── json_utils.py      # JSON 增强解析
│   ├── logger.py          # 日志
│   └── exceptions.py      # 异常定义
├── .env
├── main.py
├── run_task.py
├── pyproject.toml
└── workflow.db
```

---

## 核心功能

| 功能 | 说明 |
|------|------|
| **多源需求输入** | 支持纯文本 / PDF 上传 / 飞书 / 语雀 / TAPD / 石墨 / Confluence 链接 |
| **7 节点工作流** | 需求解析 → 测试点提取 → 去重 → 用例生成 → 审查 → 覆盖率 → 缺口填充 |
| **断点恢复** | 节点失败后从断点恢复执行，跳过已完成节点，不重复消耗 Token |
| **Token 统计持久化** | 每个节点的 Token 用量写入 SQLite，重启/重试自动累加 |
| **多格式输出** | JSON / Markdown / XMind 8 / XMind 2023 |
| **PDF 智能解析** | 文本提取 + 多模态 OCR 双通道，处理扫描件和图片 |

---

## 技术栈

| 分类 | 技术 | 版本 |
|------|------|------|
| 后端 | Python | 3.11+ |
| Web 框架 | FastAPI | - |
| AI 框架 | agent_framework | - |
| 数据库 | SQLite | 内置 |
| PDF 解析 | PyMuPDF | - |
| 依赖管理 | UV | - |

---

## 快速开始

### 1. 安装依赖

```bash
uv install
```

### 2. 配置环境变量

编辑 `.env`：

```ini
# LLM 配置（必填）
OPENAI_API_KEY=your_api_key
OPENAI_CHAT_MODEL_ID=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1

# 服务器
SERVER_HOST=0.0.0.0
SERVER_PORT=8001

# 日志
LOG_LEVEL=INFO

# 文档平台 Token（按需配置）
FEISHU_USER_ACCESS_TOKEN=        # 飞书
YUQUE_API_TOKEN=                 # 语雀
TAPD_API_USER=                   # TAPD
TAPD_API_PASSWORD=               # TAPD
SHIMO_CLIENT_ID=                 # 石墨
SHIMO_CLIENT_SECRET=             # 石墨
SHIMO_API_TOKEN=                 # 石墨
CONFLUENCE_BASE_URL=             # Confluence
CONFLUENCE_EMAIL=                # Confluence
CONFLUENCE_API_TOKEN=            # Confluence

# PDF OCR（默认 gpt-4o）
PDF_VISION_MODEL_ID=gpt-4o
PDF_MAX_PAGES=50
```

### 3. 启动服务

```bash
python main.py
```

访问 `http://localhost:8001/docs` 查看 API 文档。

---

## API 接口

### 提交任务

**POST** `/run`

支持三种输入方式（优先级：file > doc_url > task）：

```bash
# 纯文本
curl -X POST http://localhost:8001/run \
  -F "task=用户登录功能的需求文档..."

# 上传 PDF
curl -X POST http://localhost:8001/run \
  -F "file=@requirements.pdf"

# 飞书文档链接
curl -X POST http://localhost:8001/run \
  -F "doc_url=https://feishu.cn/docx/xxxxx"

# 语雀文档链接
curl -X POST http://localhost:8001/run \
  -F "doc_url=https://yuque.com/group/repo/slug"
```

**响应**：
```json
{"task_id": "550e8400-e29b-41d4-a716-446655440000"}
```

### 查询状态

**GET** `/task/{task_id}`

```json
{
  "id": "550e8400-...",
  "status": "running",
  "created_at": "2026-05-17T10:30:00",
  "updated_at": "2026-05-17T10:35:00"
}
```

### 获取结果

**GET** `/result/{task_id}`

返回多格式结果：

```json
{
  "result": {
    "json": [...],
    "markdown": "# 测试用例文档\n...",
    "xmind": {
      "xmind_8": "base64...",
      "xmind_2023": "base64...",
      "xmind_8_filename": "task_id_xmind8.xmind",
      "xmind_2023_filename": "task_id_xmind2023.xmind"
    }
  },
  "files": {
    "json": "/path/to/task_id.json",
    "markdown": "/path/to/task_id.md",
    "xmind_8": "/path/to/task_id_xmind8.xmind",
    "xmind_2023": "/path/to/task_id_xmind2023.xmind"
  }
}
```

### 获取日志

**GET** `/logs/{task_id}`

---

## 工作流

```
需求解析 → 测试点提取 → 测试点去重 → 测试用例生成 → 用例审查 → 覆盖率分析 → 缺口填充
   ↓           ↓           ↓            ↓            ↓           ↓            ↓
 Markdown    JSON        JSON         JSON        Markdown    Markdown       JSON
```

| 节点 | 输入 | 输出格式 | 说明 |
|------|------|----------|------|
| requirement | 原始需求 | Markdown | 解析需求，提取模块/角色/规则/边界 |
| testpoint | 需求信息 | JSON | 提取测试点列表 |
| dedup | 测试点列表 | JSON | 去除重复测试点 |
| testcase | 去重后测试点 | JSON | 生成完整测试用例 |
| review | 用例 + 需求 | Markdown | 审查评分、问题列表、优化建议 |
| coverage | 用例 + 需求 | Markdown | 覆盖率百分比、风险等级、未覆盖场景 |
| gap | 全部上下文 | JSON | 补充缺失用例，输出最终用例集 |

### 断点恢复

节点失败后，系统自动检测已完成节点，重试时从断点恢复：

```
[INFO] 任务执行失败，发现已完成节点 [testcase]，下次重试将从断点恢复
[INFO] 从断点恢复: 已完成节点: 3
[INFO] 加载已完成节点的缓存结果...
[INFO] 节点开始: [review] (从断点恢复)
```

### Token 统计

任务完成后自动输出每个节点的 Token 用量，数据持久化到数据库，重启不丢失：

```json
{
  "workflow": {"input_tokens": 19843, "output_tokens": 11879, "total_tokens": 31722},
  "nodes": [
    {"name": "requirement", "input": 1000, "output": 500, "total": 1500},
    {"name": "testpoint",   "input": 2000, "output": 1000, "total": 3000},
    {"name": "gap",         "input": 5000, "output": 3000, "total": 8000}
  ]
}
```

---

## 文档平台支持

| 平台 | 配置项 | 支持的资源类型 |
|------|--------|---------------|
| 飞书 | `FEISHU_USER_ACCESS_TOKEN` | 文档 / 知识库 / 多维表格 |
| 语雀 | `YUQUE_API_TOKEN` | 知识库文档 |
| TAPD | `TAPD_API_USER` + `TAPD_API_PASSWORD` | 需求/缺陷 |
| 石墨 | `SHIMO_CLIENT_ID` + `SHIMO_CLIENT_SECRET` + `SHIMO_API_TOKEN` | 文档 |
| Confluence | `CONFLUENCE_BASE_URL` + `CONFLUENCE_EMAIL` + `CONFLUENCE_API_TOKEN` | Wiki 页面 |

扩展新平台只需在 `utils/parsers/` 下新建文件，使用 `@register("domain.com")` 装饰器注册即可。

---

## PDF 解析

采用双通道策略：

- **文本页**：直接提取文本（快速、零成本）
- **扫描件/图片页**：页面转图片 → 多模态模型 OCR（处理扫描件、截图）

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `PDF_VISION_MODEL_ID` | `gpt-4o` | OCR 模型 |
| `PDF_MAX_PAGES` | `50` | 最大页数 |
| `PDF_TEXT_THRESHOLD` | `50` | 低于此字符数触发 OCR |
| `MAX_FILE_SIZE` | `10MB` | 文件大小限制 |

---

## 配置说明

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `OPENAI_API_KEY` | LLM API Key | - |
| `OPENAI_CHAT_MODEL_ID` | 默认模型 | `gpt-4o-mini` |
| `OPENAI_BASE_URL` | API 地址 | `https://api.openai.com/v1` |
| `SERVER_HOST` | 监听地址 | `0.0.0.0` |
| `SERVER_PORT` | 监听端口 | `8001` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `AGENT_TIMEOUT_SECONDS` | 节点超时 | `1000` |
| `REVIEW_MODEL_ID` | 审查节点模型 | `gpt-4o` |
| `COVERAGE_MODEL_ID` | 覆盖率节点模型 | `gpt-4o-mini` |

---

## 数据库

SQLite，文件 `workflow.db`：

| 表 | 说明 |
|----|------|
| `tasks` | 任务信息 |
| `logs` | 任务日志 |
| `node_status` | 节点状态 + 结果 + Token 统计 |

---

## 命令行运行

```bash
python run_task.py
```

---

## 许可证

MIT License
