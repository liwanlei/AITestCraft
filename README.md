# AITestCraft

AITestCraft 是一个基于 AI 的测试用例生成和管理系统，通过自动化流程从需求文档生成高质量的测试用例。

## 项目结构

```
AITestCraft/
├── agents/           # 代理相关代码
├── api/              # API 接口实现
├── config/           # 配置文件
├── core/             # 核心功能（工作流和任务执行）
├── logs/             # 日志文件
├── skills/           # 各种技能模块
│   ├── gap-filler/           # 测试用例空白填充
│   ├── requirement-parser/   # 需求文档解析
│   ├── testcase-coverage/    # 测试用例覆盖率分析
│   ├── testcase-generator/   # 测试用例生成
│   ├── testcase-reviewer/    # 测试用例审查
│   ├── testpoint-deduplicator/ # 测试点去重
│   └── testpoint-extractor/  # 测试点提取
├── storage/          # 存储相关（数据库操作）
├── utils/            # 工具函数
├── .env              # 环境变量
├── main.py           # 主入口文件
├── mainruntask.py    # 任务运行入口
├── pyproject.toml    # 项目依赖配置
├── uv.lock           # 依赖锁文件
└── workflow.db       # 工作流数据库
```

## 核心功能

- **需求解析**：自动解析需求文档，提取关键信息
- **测试点提取**：从需求中提取测试点
- **测试点去重**：去除重复的测试点
- **测试用例生成**：基于测试点生成测试用例
- **测试用例审查**：对生成的测试用例进行审查
- **测试用例覆盖率分析**：分析测试用例的覆盖率
- **测试用例空白填充**：填充测试用例中的空白部分

## 技术栈

- **后端**：Python 3.11+
- **Web 框架**：FastAPI
- **数据库**：SQLite
- **依赖管理**：UV
- **AI 框架**：agent_framework

## 快速开始

### 1. 安装依赖

```bash
# 使用 UV 安装依赖
uv install
```

### 2. 配置环境变量

复制envexplame 到 `.env` 文件，设置必要的环境变量：

```
# 示例环境变量
OPENAI_API_KEY=你的key
OPENAI_CHAT_MODEL_ID=你的模型
OPENAI_BASE_URL=请求地址
```

### 3. 启动服务

```bash
python main.py
```

服务将在 `http://0.0.0.0:8000` 启动。

## API 接口

### 1. 运行任务

**POST** `/run`

**请求体**：
```json
{
  "task": "你的需求文档内容"
}
```

**响应**：
```json
{
  "task_id": "任务ID"
}
```

### 2. 查询任务状态

**GET** `/task/{task_id}`

**响应**：
```json
{
  "id": "任务ID",
  "task": "任务内容",
  "status": "任务状态",
  "created_at": "创建时间",
  "updated_at": "更新时间"
}
```

### 3. 获取任务结果

**GET** `/result/{task_id}`

**响应**：
```json
{
  "result": "任务结果"
}
```

## 工作流程

1. 客户端发送任务到 `/run` 接口
2. 系统创建任务并异步执行
3. 执行过程包括以下步骤：
   - 需求解析
   - 测试点提取
   - 测试点去重
   - 测试用例生成
   - 测试用例审查
   - 测试用例覆盖率分析
   - 测试用例空白填充
4. 客户端可以通过 `/task/{task_id}` 查询任务状态
5. 客户端可以通过 `/result/{task_id}` 获取任务结果

## 技能模块

AITestCraft 包含以下技能模块：

- **requirement-parser**：解析需求文档，提取关键信息
- **testpoint-extractor**：从需求中提取测试点
- **testpoint-deduplicator**：去除重复的测试点
- **testcase-generator**：基于测试点生成测试用例
- **testcase-reviewer**：对生成的测试用例进行审查
- **testcase-coverage**：分析测试用例的覆盖率
- **gap-filler**：填充测试用例中的空白部分

## 日志

系统日志存储在 `logs/AITestCraft.log` 文件中。

## 数据库

系统使用 SQLite 数据库存储任务信息，数据库文件为 `workflow.db`。

## 不用现在的接口
 参考mainruntask.py即可

## 许可证

MIT License
