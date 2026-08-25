# 需求知识提取（Knowledge Extraction）设计文档

## 1. 背景与目标

### 1.1 背景

现有 AITestCraft 工作流是**正向生成**：`需求 → 测试点 → 测试用例`。但在实际业务中，测试团队往往已经积累了大量历史用例，这些用例中蕴含着产品的需求知识（功能点、业务规则、边界条件、异常场景）。如果能将这些用例逆向归纳为结构化的需求知识点，并沉淀为知识库，就能在后续的新需求测试中提供历史参考，提升用例设计的完整性和一致性。

### 1.2 目标

- **独立任务**：支持用户传入一批用例 ID，系统异步提取归纳需求知识点
- **冲突解决**：当不同用例对同一场景的描述矛盾时，以用例 ID 大的为准（代表新版本），并记录变更历史
- **知识库沉淀**：归纳结果以 Markdown + 结构化 JSON 双格式存储，支持后续查询和复用
- **手动关联复用**：在生成新测试用例时，用户可手动选择关联知识库，系统将其作为上下文注入需求解析节点

---

## 2. 架构设计

### 2.1 整体定位

新增 **Knowledge Extraction 工作流**，与现有 **Testcase Generation 工作流**平行共存，复用同一套基础设施：

- 任务调度与状态管理（SQLite `tasks` 表）
- 断点恢复与 Token 统计
- 日志系统
- Agent / SkillsProvider 机制

```
┌─────────────────────────────────────────────────────────────┐
│                     AITestCraft API Layer                    │
├──────────────────────────────┬──────────────────────────────┤
│   Testcase Generation Flow   │  Knowledge Extraction Flow   │
│                              │                              │
│  requirement → testpoint    │  fetch-cases                 │
│     → testcase → review     │    → summarize-modules       │
│     → coverage → gap        │    → dedup                   │
│                              │    → resolve-conflicts       │
│                              │    → consolidate-knowledge   │
└──────────────────────────────┴──────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   Knowledge Base  │
                    │   (SQLite Table)  │
└──────────────────┴──────────────────┘
```

### 2.2 复用策略

- `tasks` 表增加 `task_type` 字段（`testcase` / `knowledge`），复用现有状态机
- `node_status` 表同样复用，记录知识提取各节点的执行状态和结果
- 新增 `knowledge_bases` 和 `knowledge_items` 两张表专门存储知识库数据

---

## 3. 工作流节点设计（5 节点）

### 3.1 节点总览

| 节点 | 职责 | Agent Skill | 输入 | 输出 |
|------|------|-------------|------|------|
| **fetch-cases** | 获取并解析用例 | `AITestCraft-fetch-cases` | 用例 ID 列表 | 标准化用例 JSON 数组 |
| **summarize-modules** | 按模块归纳需求知识点 | `AITestCraft-summarize-modules` | 标准化用例数组 | 各模块需求知识 Markdown |
| **dedup** | 全局语义去重 | `AITestCraft-dedup` | 各模块 Markdown | 去重后知识点数组 |
| **resolve-conflicts** | 冲突检测与解决 | `AITestCraft-resolve-conflicts` | 去重后知识点数组 | 冲突解决后知识点数组 |
| **consolidate-knowledge** | 汇总格式化并持久化 | `AITestCraft-consolidate-knowledge` | 冲突解决后数组 | Markdown + 结构化 JSON |

### 3.2 fetch-cases 节点

**职责**：并发调用第三方用例服务，获取原始用例数据，通过**树形解析器**扁平化为标准格式。

**输入**：
```json
{
  "case_ids": ["TC001", "TC002", "TC005"]
}
```

**第三方原始格式**（`api/case/getCaseJson` 返回）：

```json
{
  "code": 200,
  "msg": "服务运行成功",
  "data": {
    "caseContent": {
      "template": "right",
      "root": {
        "data": {
          "id": "qq344b422bbf",
          "text": "手机号登录",
          "created": 1780753285449
        },
        "children": [
          {
            "data": {
              "id": "snh4v86c0che",
              "text": "[P0] TC001: 验证码登录-有效手机号验证码登录-登录成功跳转首页",
              "created": 1780753285449
            },
            "children": [
              {
                "data": {
                  "id": "kp6a5s6ladxo",
                  "resource": ["前置条件"],
                  "text": "用户未登录，已注册手机号13800000001，可正常接收短信"
                }
              },
              {
                "data": {
                  "id": "m055mix4leyj",
                  "resource": ["执行步骤"],
                  "text": "1. 打开登录页面"
                },
                "children": [
                  {
                    "data": {
                      "id": "nmtj6r53gv3b",
                      "resource": ["执行步骤"],
                      "text": "2. 输入手机号13800000001"
                    },
                    "children": [
                      // ... 链式嵌套
                    ]
                  }
                ]
              },
              {
                "data": {
                  "id": "8voqk4hb2q2c",
                  "resource": ["预期结果"],
                  "text": "页面跳转至首页，显示用户昵称"
                }
              }
            ]
          }
        ]
      }
    }
  }
}
```

**解析规则**：

1. **根节点** `root.data.text` → 模块名（如「手机号登录」）
2. **第一层子节点** `root.children` 的每个元素是一条用例
   - `text` 格式：`[优先级] 用例ID: 模块-场景-预期结果`
   - 解析正则：`\[(P[012])\]\s*(TC\d+):\s*(.+)`
3. **第二层及以下**：通过 `resource` 字段区分
   - `["前置条件"]` → `precondition`
   - `["执行步骤"]` → `steps`（收集所有步骤节点，按出现顺序）
   - `["预期结果"]` → `assert`（收集所有预期结果节点）
4. **步骤链式结构**：执行步骤节点通过 `children` 链式嵌套，需递归展开为数组

**输出标准格式**：

```json
[
  {
    "case_id": "TC001",
    "module": "手机号登录",
    "priority": "P0",
    "name": "验证码登录-有效手机号验证码登录-登录成功跳转首页",
    "precondition": "用户未登录，已注册手机号13800000001，可正常接收短信",
    "steps": [
      "打开登录页面",
      "输入手机号13800000001",
      "点击「获取验证码」按钮",
      "在验证码输入框输入收到的6位正确验证码",
      "点击「登录」按钮"
    ],
    "assert": [
      "页面跳转至首页，显示用户昵称"
    ]
  }
]
```

**并发策略**：
- 使用 `asyncio.gather` 并发获取，并发数由配置 `KNOWLEDGE_FETCH_CONCURRENCY` 控制（默认 5）
- 单个用例获取超时由 `KNOWLEDGE_FETCH_TIMEOUT` 控制（默认 30 秒）

### 3.3 summarize-modules 节点

**职责**：按模块分组，对每个模块的用例集合调用 LLM，逆向归纳出需求知识点。

**输入**：标准化用例 JSON 数组

**Prompt 设计要点**：
- 角色：需求分析师，擅长从测试用例中反推产品需求
- 任务：根据输入的测试用例，归纳出该模块的需求知识点
- 输出维度：功能点、业务规则、边界条件、异常场景
- 每条知识点必须标注来源用例 ID（用于后续冲突解决）

**输出格式**（Markdown）：

```markdown
## 模块：手机号登录

### 功能点
- 手机号验证码登录（来源：TC001, TC002）
- 密码登录（来源：TC003）

### 业务规则
- 验证码为6位数字（来源：TC001）
- 验证码有效期5分钟（来源：TC001）
- 同手机号发送间隔60秒（来源：TC002）

### 边界条件
- 验证码刚好过期（来源：TC001）
- 手机号带+86前缀（来源：TC001）

### 异常场景
- 验证码错误（来源：TC002）
- 验证码过期（来源：TC002）
```

### 3.4 dedup 节点

**职责**：全局语义去重，识别不同模块中语义重复或高度相似的知识点。

**去重规则**：
1. 场景相同 + 行为相同 + 断言目标一致 → 重复
2. 语义高度相似（如「验证码为6位数字」和「验证码必须是6位数字」）→ 合并
3. 不同模块中相似但上下文不同的 → 保留（如登录模块的「密码错误」和修改密码模块的「密码错误」不重复）

**输出**：去重后的知识点数组（JSON），每条包含 `content`, `module`, `item_type`, `source_case_ids`

### 3.5 resolve-conflicts 节点

**职责**：检测并解决同一模块、同一场景/规则但描述矛盾的需求知识点。

**冲突检测条件**：
- 同一 `module`
- 同一 `item_type`（如都是「业务规则」）
- 同一功能点/规则场景
- 但 `content` 描述矛盾（如一个说有效期 5 分钟，另一个说 10 分钟）

**冲突解决规则**：
- 比较来源用例 ID，**用例 ID 大的代表新版本，优先采纳**
- 被覆盖的旧版本知识点标记为 `status: changed`
- 记录 `old_content` 和 `change_reason`

**示例**：

| 知识点 | 来源用例 | 处理结果 |
|--------|----------|----------|
| 验证码有效期 5 分钟 | TC001 | status=changed, old_content=验证码有效期 5 分钟, change_reason=用例 TC005 覆盖：需求更新为 10 分钟 |
| 验证码有效期 10 分钟 | TC005 | status=active |

**输出**：冲突解决后的知识点数组（JSON）

### 3.6 consolidate-knowledge 节点

**职责**：汇总所有模块的知识点，格式化输出 Markdown 文档和结构化 JSON，并持久化到数据库。

**输出格式**：

1. **Markdown 文档**：按模块分组，包含功能点、业务规则、边界条件、异常场景，以及变更历史附录
2. **结构化 JSON**：

```json
{
  "title": "手机号登录-需求知识点",
  "modules": ["手机号登录", "密码登录"],
  "items": [
    {
      "id": "ki_001",
      "module": "手机号登录",
      "item_type": "rule",
      "content": "验证码有效期 10 分钟",
      "priority": "P0",
      "source_case_ids": ["TC005"],
      "status": "active"
    },
    {
      "id": "ki_002",
      "module": "手机号登录",
      "item_type": "rule",
      "content": "验证码有效期 5 分钟",
      "priority": "P0",
      "source_case_ids": ["TC001"],
      "status": "changed",
      "old_content": "验证码有效期 5 分钟",
      "change_reason": "用例 TC005 覆盖：需求更新为 10 分钟"
    }
  ]
}
```

**持久化**：
- 写入 `knowledge_bases` 表（主记录）
- 写入 `knowledge_items` 表（明细记录）

---

## 4. 数据模型

### 4.1 knowledge_bases（知识库主表）

```sql
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    markdown_content TEXT,
    modules_json TEXT,          -- JSON 数组：["手机号登录", "密码登录"]
    source_case_ids TEXT,       -- JSON 数组：["TC001", "TC002"]
    status TEXT DEFAULT 'active', -- active / archived
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

### 4.2 knowledge_items（知识点明细表）

```sql
CREATE TABLE IF NOT EXISTS knowledge_items (
    id TEXT PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL,
    module TEXT NOT NULL,
    item_type TEXT NOT NULL,     -- functional / rule / boundary / exception
    content TEXT NOT NULL,
    priority TEXT,               -- P0 / P1 / P2
    source_case_ids TEXT,        -- JSON 数组
    status TEXT DEFAULT 'active', -- active / changed / deprecated
    old_content TEXT,
    change_reason TEXT,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id)
);
```

### 4.3 tasks 表扩展

现有 `tasks` 表增加 `task_type` 字段：

```sql
ALTER TABLE tasks ADD COLUMN task_type TEXT DEFAULT 'testcase';
```

取值：
- `testcase`：现有测试用例生成任务
- `knowledge`：需求知识提取任务

---

## 5. API 接口设计

### 5.1 提交知识提取任务

```http
POST /api/knowledge/extract
```

**请求体**：

```json
{
  "case_ids": ["TC001", "TC002", "TC005"]
}
```

**响应**：

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 5.2 查询任务状态

```http
GET /api/knowledge/tasks/{task_id}
```

**响应**（复用现有 StatusResponse 结构）：

```json
{
  "id": "550e8400-...",
  "task": "knowledge extraction for TC001,TC002,TC005",
  "status": "success",
  "created_at": "2026-06-13T10:30:00",
  "updated_at": "2026-06-13T10:35:00"
}
```

### 5.3 获取任务结果

```http
GET /api/knowledge/tasks/{task_id}/result
```

**响应**：

```json
{
  "knowledge_base_id": "kb_abc123",
  "markdown": "## 模块：手机号登录\n\n### 功能点\n...",
  "modules": ["手机号登录", "密码登录"],
  "item_count": 15,
  "change_count": 2
}
```

### 5.4 查询知识库列表

```http
GET /api/knowledge/bases
```

**响应**：

```json
{
  "total": 10,
  "items": [
    {
      "id": "kb_abc123",
      "title": "手机号登录-需求知识点",
      "module_count": 2,
      "item_count": 15,
      "created_at": "2026-06-13T10:35:00"
    }
  ]
}
```

### 5.5 查询知识库详情

```http
GET /api/knowledge/bases/{knowledge_base_id}
```

**响应**：

```json
{
  "id": "kb_abc123",
  "title": "手机号登录-需求知识点",
  "markdown": "## 模块：手机号登录\n...",
  "modules": ["手机号登录", "密码登录"],
  "items": [
    {
      "id": "ki_001",
      "module": "手机号登录",
      "item_type": "rule",
      "content": "验证码有效期 10 分钟",
      "priority": "P0",
      "source_case_ids": ["TC005"],
      "status": "active"
    }
  ],
  "changes": [
    {
      "id": "ki_002",
      "module": "手机号登录",
      "item_type": "rule",
      "old_content": "验证码有效期 5 分钟",
      "new_content": "验证码有效期 10 分钟",
      "change_reason": "用例 TC005 覆盖：需求更新为 10 分钟"
    }
  ]
}
```

### 5.6 扩展现有 /run 接口

```http
POST /api/run
```

**请求体扩展**：

```json
{
  "task": "用户登录功能需求...",
  "knowledge_base_ids": ["kb_abc123"],
  "doc_url": "https://feishu.cn/docx/xxxxx"
}
```

**逻辑**：如果提供了 `knowledge_base_ids`，在 `requirement-parser` 节点的输入中自动注入关联知识库的知识点上下文。

---

## 6. 错误处理

| 场景 | 处理策略 |
|------|----------|
| `getCaseJson` 单个 ID 失败 | 记录警告日志，跳过该用例，继续处理其他。最终结果中标注「部分用例获取失败」 |
| `getCaseJson` 全部失败 | 任务直接标记 `failed`，返回错误信息「所有用例获取失败」 |
| LLM 节点超时/失败 | 复用现有 `run_with_retry` 机制，重试 3 次后标记任务 `failed` |
| 去重/冲突节点无输入 | 空安全处理，输出空知识库，任务标记 `success`，结果为空 |
| 树形解析异常 | 跳过该用例，记录解析错误，继续处理其他 |

---

## 7. 配置项

在 `config/config.py` 中新增：

```python
# 外部用例服务配置
CASE_SERVICE_BASE_URL: str = os.getenv("CASE_SERVICE_BASE_URL", "")
CASE_SERVICE_GET_CASE_API: str = os.getenv("CASE_SERVICE_GET_CASE_API", "/api/case/getCaseJson")

# 知识提取工作流配置
KNOWLEDGE_FETCH_TIMEOUT: int = _get_env_int("KNOWLEDGE_FETCH_TIMEOUT", 30)
KNOWLEDGE_FETCH_CONCURRENCY: int = _get_env_int("KNOWLEDGE_FETCH_CONCURRENCY", 5)
```

---

## 8. Skill 定义

新增 5 个 Skill 目录和 `SKILL.md`：

- `skills/AITestCraft-fetch-cases/SKILL.md`
- `skills/AITestCraft-summarize-modules/SKILL.md`
- `skills/AITestCraft-dedup/SKILL.md`
- `skills/AITestCraft-resolve-conflicts/SKILL.md`
- `skills/AITestCraft-consolidate-knowledge/SKILL.md`

各 Skill 的 `name` 字段统一使用 `AITestCraft-` 前缀，与现有 skill 命名规范保持一致。

---

## 9. 与现有系统的集成

### 9.1 任务管理复用

- `tasks` 表通过 `task_type` 区分任务类型
- `knowledge` 类型任务复用同样的状态流转：`pending → running → success/failed`
- 日志、Token 统计、断点恢复机制完全复用

### 9.2 知识库注入需求解析

在 `requirement-parser` 的 Prompt 模板中，增加可选的「历史需求知识库」章节：

```markdown
## 历史需求知识库
（以下知识点来自已归纳的历史用例，请在新需求解析中参考并标注变化）

### 手机号登录
- 验证码为6位数字
- 验证码有效期 10 分钟（注意：历史版本为 5 分钟）
- ...

{{knowledge_context}}
```

注入逻辑在 `_build_requirement_input` 中实现：如果 `ctx` 中存在 `knowledge_context`，则追加到输入中。

---

## 10. 测试策略

| 测试项 | 说明 |
|--------|------|
| 树形解析器单元测试 | 覆盖正常解析、缺 resource 字段、循环 children、空 children 等边界 |
| fetch-cases 并发测试 | 模拟部分外部 API 失败，验证容错和结果完整性 |
| 冲突解决单元测试 | 构造矛盾知识点，验证 ID 大的优先和变更记录正确性 |
| 端到端集成测试 | 提交知识提取任务，验证全流程状态流转和数据库持久化 |
| API 接口测试 | 测试各新增接口的入参校验、错误码、响应格式 |

---

## 11. 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 第三方用例格式变更 | 树形解析器失效 | 解析器增加版本兼容层，格式异常时降级为原始文本 |
| 大批量用例（>100） | LLM 上下文溢出 | fetch-cases 节点增加分批逻辑，summarize-modules 按批次处理 |
| 冲突检测误报 | 错误标记变更 | resolve-conflicts 的冲突判定规则保守设计，仅处理明确矛盾 |
