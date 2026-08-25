# 大需求分块处理测试用例生成 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将大需求按模块拆分并行提取测试点，全局去重后按模块分组输出测试用例，降低大需求用例遗漏率。

**Architecture:** 在现有 7 节点工作流中，增强 requirement-parser 输出模块化结构，testpoint-extractor 支持多模块并行提取，新增 module-aggregator 节点合并去重并按模块分组，testcase-generator 按模块逐个生成用例。小需求（模块数 ≤ 阈值）自动退化为原有单流程。

**Tech Stack:** Python 3.10+, asyncio, 现有 agent_framework

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `config/config.py` | 修改 | 新增分块配置项 |
| `skills/requirement-parser/SKILL.md` | 修改 | 增加模块拆分输出格式 |
| `skills/testpoint-extractor/SKILL.md` | 修改 | 支持单模块输入 |
| `skills/module-aggregator/SKILL.md` | 新增 | 模块汇总去重技能定义 |
| `skills/testcase-generator/SKILL.md` | 修改 | 支持按模块分组输出 |
| `core/workflow_builders.py` | 修改 | 重构为支持分块的新工作流 |
| `core/workflow.py` | 修改 | 新增并行执行能力 |
| `core/taskexecution.py` | 修改 | 适配新工作流结果格式 |
| `formatters/markdown_formatter.py` | 修改 | 支持按模块分组输出 |
| `formatters/xmind_formatter.py` | 修改 | 支持按模块分组输出 |

---

### Task 1: 新增配置项

**Files:**
- Modify: `config/config.py`

- [ ] **Step 1: 在 Config 类中新增分块配置**

在 `config/config.py` 的 `Config` 类中，在 `AGENT_TIMEOUT_SECONDS` 之后添加：

```python
    MODULE_SPLIT_THRESHOLD: int = _get_env_int("MODULE_SPLIT_THRESHOLD", 3)
    MODULE_MAX_TOKENS: int = _get_env_int("MODULE_MAX_TOKENS", 4000)
```

- [ ] **Step 2: 在 SKILL_NAMES 中新增 aggregator 映射**

在 `config/config.py` 的 `SKILL_NAMES` 字典中，在 `"gap"` 行之后添加：

```python
        "aggregator": "module-aggregator",
```

- [ ] **Step 3: 验证配置加载**

Run: `cd /Users/lileilei/Desktop/AITestCraft && python3 -c "from config.config import Config; print(f'Threshold={Config.MODULE_SPLIT_THRESHOLD}, MaxTokens={Config.MODULE_MAX_TOKENS}'); print(f'Skills={Config.SKILL_NAMES}')"`
Expected: 输出包含 `Threshold=3, MaxTokens=4000` 和 `aggregator` 键

- [ ] **Step 4: Commit**

```bash
git add config/config.py
git commit -m "feat: add module split config and aggregator skill mapping"
```

---

### Task 2: 修改 requirement-parser SKILL.md

**Files:**
- Modify: `skills/requirement-parser/SKILL.md`

- [ ] **Step 1: 重写 SKILL.md 增加模块拆分输出**

将 `skills/requirement-parser/SKILL.md` 的完整内容替换为：

```markdown
---
name: requirement-parser
description: >
  解析产品需求，将自然语言需求转为结构化需求信息，并按功能模块拆分。
version: 5.0
author: leizi
---

# ROLE
你是测试需求解析引擎（Requirement Parser）。

# TASK
从用户需求中提取关键测试信息，并按功能模块拆分。

## 提取维度
- 功能模块
- 用户角色
- 输入数据
- 操作行为
- 系统响应
- 业务规则
- 边界条件
- 异常场景

## 模块拆分规则
1. 按功能独立性拆分模块（如：登录、注册、支付、订单管理）
2. 每个模块必须包含完整的需求描述
3. 模块按业务重要性标注优先级（P0/P1/P2）
4. 模块之间避免内容重叠
5. 小需求（单一功能）只输出1个模块

# INPUT
需求描述：
{{input}}

# OUTPUT
严格输出 Markdown 格式，按以下结构组织：

## 模块列表

| 模块ID | 模块名称 | 优先级 | 需求描述 |
|--------|----------|--------|----------|
| M1 | [模块名] | P0/P1/P2 | [该模块的完整需求描述] |
| M2 | [模块名] | P0/P1/P2 | [该模块的完整需求描述] |

## M1: [模块名称]

### 用户角色
- [角色1]

### 输入数据
- [输入1]

### 操作行为
- [行为1]

### 系统响应
- [响应1]

### 业务规则
- [规则1]

### 边界条件
- [边界1]

### 异常场景
- [异常1]

## M2: [模块名称]

（同上结构）

# RULES
- 只输出 Markdown 格式
- 所有文本内容必须使用中文
- 禁止输出 JSON
- 禁止输出解释
- 禁止输出 ```json 代码块
- 必须按上述 Markdown 结构输出
- 模块列表表格必须包含所有模块
- 每个模块的详细描述必须完整，不依赖其他模块

# EXAMPLE
输入：
手机号验证码登录，验证码6位数字，有效期5分钟，同手机号发送间隔60秒。支持密码登录，密码8-20位，包含字母和数字。

输出：
## 模块列表

| 模块ID | 模块名称 | 优先级 | 需求描述 |
|--------|----------|--------|----------|
| M1 | 验证码登录 | P0 | 手机号验证码登录，验证码6位数字，有效期5分钟，同手机号发送间隔60秒 |
| M2 | 密码登录 | P1 | 支持密码登录，密码8-20位，包含字母和数字 |

## M1: 验证码登录

### 用户角色
- 未登录用户

### 输入数据
- 手机号
- 6位数字验证码

### 操作行为
- 输入手机号
- 获取验证码
- 输入验证码
- 点击登录

### 系统响应
- 登录成功跳转首页
- 验证码错误提示
- 验证码过期提示

### 业务规则
- 验证码6位数字
- 有效期5分钟
- 同手机号发送间隔60秒

### 边界条件
- 验证码刚好过期
- 手机号带+86前缀

### 异常场景
- 验证码错误
- 验证码过期
- 手机号格式错误

## M2: 密码登录

### 用户角色
- 未登录用户

### 输入数据
- 手机号
- 8-20位密码

### 操作行为
- 输入手机号
- 输入密码
- 点击登录

### 系统响应
- 登录成功跳转首页
- 密码错误提示

### 业务规则
- 密码8-20位
- 必须包含字母和数字

### 边界条件
- 密码刚好8位
- 密码刚好20位

### 异常场景
- 密码错误
- 密码格式不合规
```

- [ ] **Step 2: Commit**

```bash
git add skills/requirement-parser/SKILL.md
git commit -m "feat: upgrade requirement-parser to support module splitting"
```

---

### Task 3: 修改 testpoint-extractor SKILL.md

**Files:**
- Modify: `skills/testpoint-extractor/SKILL.md`

- [ ] **Step 1: 重写 SKILL.md 支持单模块输入**

将 `skills/testpoint-extractor/SKILL.md` 的完整内容替换为：

```markdown
---
name: testpoint-extractor
description: >
  根据需求结构生成测试点列表。支持单模块输入。
version: 5.0
author: leizi
---

# ROLE
你是测试点生成引擎（Test Point Extractor）。

# TASK
根据需求信息生成测试点。输入可能是完整需求或单个模块的需求。

## 覆盖维度
1. 正常流程
2. 输入校验
3. 边界条件
4. 异常流程
5. 权限控制
6. 安全风险

# INPUT
需求结构：
{{input}}

# OUTPUT
严格输出 Markdown 格式，按以下结构组织：

| ID | 模块 | 类型 | 测试点 | 优先级 |
|---|---|---|---|---|
| TP001 | [模块] | [类型] | [测试点描述] | P0/P1/P2 |

类型可选值：functional / boundary / exception / security / performance / compatibility

# RULES
- 只输出 Markdown 表格格式
- 所有文本内容必须使用中文
- 禁止输出 JSON
- 禁止输出解释
- 禁止输出 ```json 代码块
- 每个测试点必须精确、可验证
- 不遗漏任何业务规则和边界条件

# EXAMPLE
输入：
## M1: 验证码登录

### 用户角色
- 未登录用户

### 输入数据
- 手机号
- 6位数字验证码

### 操作行为
- 输入手机号
- 获取验证码
- 输入验证码
- 点击登录

### 业务规则
- 验证码6位数字
- 有效期5分钟
- 同手机号发送间隔60秒

输出：
| ID | 模块 | 类型 | 测试点 | 优先级 |
|---|---|---|---|---|
| TP001 | 验证码登录 | functional | 手机号验证码正确登录 | P0 |
| TP002 | 验证码登录 | exception | 验证码错误提示 | P1 |
| TP003 | 验证码登录 | boundary | 验证码过期后输入 | P1 |
| TP004 | 验证码登录 | security | 60秒内重复发送验证码限制 | P1 |
```

- [ ] **Step 2: Commit**

```bash
git add skills/testpoint-extractor/SKILL.md
git commit -m "feat: upgrade testpoint-extractor for single-module input"
```

---

### Task 4: 新增 module-aggregator SKILL.md

**Files:**
- Create: `skills/module-aggregator/SKILL.md`

- [ ] **Step 1: 创建目录和文件**

```bash
mkdir -p skills/module-aggregator
```

创建 `skills/module-aggregator/SKILL.md`：

```markdown
---
name: module-aggregator
description: >
  模块测试点汇总引擎。合并各模块测试点，全局去重，按模块分组输出。
version: 1.0
author: leizi
---

# ROLE
你是模块测试点汇总引擎（Module Aggregator）。

# TASK
将各模块的测试点合并，进行全局去重，按模块分组输出。

## 去重规则
1. 场景相同、行为相同、断言目标一致 → 重复
2. 语义高度相似的测试点 → 合并为一个
3. 不同模块中相似但上下文不同的测试点 → 保留（如：登录模块的"密码错误"和修改密码模块的"密码错误"不重复）

## 分组规则
1. 去重后的测试点必须保留模块归属
2. 按模块分组输出
3. 每个模块内按优先级排序（P0 > P1 > P2）
4. 模块之间按模块优先级排序

# INPUT
各模块测试点（Markdown 表格格式，多个模块用分隔线隔开）：

{{input}}

# OUTPUT
严格输出 Markdown 格式：

## 去重统计
- 总输入测试点数：[N]
- 去重后测试点数：[M]
- 重复项数：[N-M]

## 按模块分组的测试点

### [模块1名称]（P0）

| ID | 模块 | 类型 | 测试点 | 优先级 |
|---|---|---|---|---|
| TP001 | [模块] | [类型] | [测试点描述] | P0/P1/P2 |

### [模块2名称]（P1）

| ID | 模块 | 类型 | 测试点 | 优先级 |
|---|---|---|---|---|
| TP005 | [模块] | [类型] | [测试点描述] | P0/P1/P2 |

## 重复项

| 原始ID | 重复ID | 原因 |
|---|---|---|
| TP001 | TP002 | 语义相同 |

# RULES
- 只输出 Markdown 格式
- 所有文本内容必须使用中文
- 禁止输出 JSON
- 禁止输出解释
- 禁止输出 ```json 代码块
- 去重后的测试点必须重新编号（TP001, TP002, ...）
- 每个测试点必须保留模块归属字段

# EXAMPLE
输入：
### 验证码登录

| ID | 模块 | 类型 | 测试点 | 优先级 |
|---|---|---|---|---|
| TP001 | 验证码登录 | functional | 手机号验证码登录 | P0 |
| TP002 | 验证码登录 | functional | 手机号和验证码登录 | P0 |

### 密码登录

| ID | 模块 | 类型 | 测试点 | 优先级 |
|---|---|---|---|---|
| TP003 | 密码登录 | functional | 手机号密码登录 | P0 |
| TP004 | 密码登录 | exception | 密码错误提示 | P1 |

输出：
## 去重统计
- 总输入测试点数：4
- 去重后测试点数：3
- 重复项数：1

## 按模块分组的测试点

### 验证码登录（P0）

| ID | 模块 | 类型 | 测试点 | 优先级 |
|---|---|---|---|---|
| TP001 | 验证码登录 | functional | 手机号验证码登录 | P0 |

### 密码登录（P1）

| ID | 模块 | 类型 | 测试点 | 优先级 |
|---|---|---|---|---|
| TP002 | 密码登录 | functional | 手机号密码登录 | P0 |
| TP003 | 密码登录 | exception | 密码错误提示 | P1 |

## 重复项

| 原始ID | 重复ID | 原因 |
|---|---|---|
| TP001 | TP002 | 语义相同：都是验证码登录 |
```

- [ ] **Step 2: Commit**

```bash
git add skills/module-aggregator/SKILL.md
git commit -m "feat: add module-aggregator skill definition"
```

---

### Task 5: 修改 testcase-generator SKILL.md

**Files:**
- Modify: `skills/testcase-generator/SKILL.md`

- [ ] **Step 1: 重写 SKILL.md 支持按模块分组输出**

将 `skills/testcase-generator/SKILL.md` 的完整内容替换为：

```markdown
---
name: testcase-generator
description: >
  生成软件测试用例。支持按模块分组输出测试用例。
version: 4.0
author: leizi
---

# ROLE
你是测试用例生成引擎（Test Case Generator）。

# TASK
根据输入的测试点列表生成可执行测试用例。输入可能包含多个模块的测试点，需按模块分组输出。

## 硬性约束（必须遵守）
1. 每个测试点至少生成 1 个用例
2. P0 测试点必须生成：1个正常流程用例 + 1个异常或边界用例
3. 用例必须满足可执行性：
   - steps 必须包含明确动作 + 对象 + 输入数据 + 结果行为
   - 禁止抽象描述（如：验证功能正常）
4. precondition 必须明确系统状态：是否登录、是否有数据、是否处于某页面
5. assert 必须满足可验证原则：必须包含可观察结果（页面展示/接口返回/数据变化/提示文案）
6. 每个用例必须至少 1 个核心 assert，P0 用例必须 >= 2 个 assert
7. 一个用例只验证一个核心行为，禁止巨型用例

## 指导性建议（尽量遵守）
1. 测试覆盖要求：
   - functional：核心流程
   - boundary：边界值（最大/最小/空/NULL）
   - exception：异常输入/错误路径
   - security：登录/权限/输入安全
2. 数据约束：必须使用真实结构化数据（手机号/用户名/ID），禁止使用 xxx 或 测试数据 等占位符
3. 状态一致性：steps 中的状态必须前后一致，不允许逻辑跳跃
4. 命名规范：name 必须包含 模块 + 场景 + 预期结果关键词
5. 优先级规则：
   - P0：核心路径/资金/登录/主流程
   - P1：功能扩展
   - P2：低频/辅助/展示类
6. 所有输入数据必须可唯一识别、可复现

# INPUT
测试点列表（按模块分组，Markdown 格式）：

### [模块1名称]

| ID | 模块 | 类型 | 测试点 | 优先级 |
|---|---|---|---|---|
| TP001 | [模块] | [类型] | [测试点描述] | P0/P1/P2 |

### [模块2名称]

| ID | 模块 | 类型 | 测试点 | 优先级 |
|---|---|---|---|---|
| TP005 | [模块] | [类型] | [测试点描述] | P0/P1/P2 |

# OUTPUT
按模块分组输出测试用例，每个模块一个表格：

### [模块1名称]

| ID | 名称 | 优先级 | 前置条件 | 测试步骤 | 预期结果 |
|----|------|--------|----------|----------|----------|
| TC001 | [模块]-[场景]-[预期] | P0 | [前置条件] | [步骤] | [预期] |

### [模块2名称]

| ID | 名称 | 优先级 | 前置条件 | 测试步骤 | 预期结果 |
|----|------|--------|----------|----------|----------|
| TC010 | [模块]-[场景]-[预期] | P1 | [前置条件] | [步骤] | [预期] |

# RULES
- 只输出 Markdown 表格
- 必须使用标准表格格式，包含所有列
- 必须包含表头行
- 单元格内换行使用 `<br>` 标签
- 不允许任何额外文本（包括解释、空行）
- 所有文本内容必须使用中文
- 按模块分组输出，模块之间用 `###` 标题分隔
- 每个模块的用例 ID 连续递增
- 用例 name 必须以模块名开头

# EXAMPLE
输入测试点：
### 验证码登录

| ID | 模块 | 类型 | 测试点 | 优先级 |
|---|---|---|---|---|
| TP001 | 验证码登录 | functional | 手机号验证码登录 | P0 |

输出：
### 验证码登录

| ID | 名称 | 优先级 | 前置条件 | 测试步骤 | 预期结果 |
|----|------|--------|----------|----------|----------|
| TC001 | 验证码登录-手机号验证码登录-登录成功 | P0 | 用户未登录，已注册手机号13800000001 | 1. 打开登录页面<br>2. 输入手机号13800000001<br>3. 点击获取验证码<br>4. 输入收到的6位验证码<br>5. 点击登录按钮 | 页面跳转至首页<br>显示用户昵称 |
```

- [ ] **Step 2: Commit**

```bash
git add skills/testcase-generator/SKILL.md
git commit -m "feat: upgrade testcase-generator for module-grouped output"
```

---

### Task 6: 重构 workflow_builders.py 支持分块工作流

**Files:**
- Modify: `core/workflow_builders.py`

这是核心变更。需要：
1. 解析 requirement-parser 输出中的模块列表
2. 多模块时并行提取测试点
3. 新增 aggregator 节点
4. 按模块分组生成用例

- [ ] **Step 1: 新增模块解析和分块输入构建函数**

在 `core/workflow_builders.py` 中，在现有 import 和函数之后添加：

```python
import asyncio


def _parse_modules(requirement_text: str) -> List[Dict[str, str]]:
    modules = []
    pattern = re.compile(
        r'\|\s*(M\d+)\s*\|\s*([^|]+?)\s*\|\s*(P[012])\s*\|\s*([^|]+?)\s*\|'
    )
    for match in pattern.finditer(requirement_text):
        modules.append({
            "id": match.group(1).strip(),
            "name": match.group(2).strip(),
            "priority": match.group(3).strip(),
            "content": match.group(4).strip()
        })
    return modules


def _extract_module_section(requirement_text: str, module_id: str) -> str:
    pattern = re.compile(
        rf'##\s*{module_id}[:\s]+(.*?)(?=##\s*M\d[:\s]|$)',
        re.DOTALL
    )
    match = pattern.search(requirement_text)
    if match:
        return f"## {module_id}: {modules_dict.get(module_id, '')}\n{match.group(1).strip()}"
    return ""


def _build_module_testpoint_inputs(ctx: Context) -> List[Dict[str, str]]:
    requirement_text = ctx.get("requirement", "")
    modules = _parse_modules(requirement_text)
    if len(modules) <= Config.MODULE_SPLIT_THRESHOLD:
        return [{"module_id": "ALL", "input": requirement_text}]
    return [
        {
            "module_id": m["id"],
            "input": f"## {m['id']}: {m['name']}\n\n{m['content']}"
        }
        for m in modules
    ]


def _build_aggregator_input(ctx: Context) -> str:
    module_testpoints = ctx.get("module_testpoints", {})
    if isinstance(module_testpoints, str):
        return module_testpoints
    parts = []
    for module_id, testpoints in module_testpoints.items():
        parts.append(f"### {module_id}\n\n{testpoints}")
    return "\n\n".join(parts)


def _build_module_testcase_input(ctx: Context) -> str:
    grouped = ctx.get("grouped_testpoints", "")
    if not grouped:
        return ctx.get("unique_testpoints", "")
    return grouped
```

- [ ] **Step 2: 重写 build_workflow 函数**

将 `build_workflow` 函数替换为：

```python
def build_workflow(agents: Dict[str, Any], model_configs: Optional[Dict[str, Dict]] = None) -> Workflow:
    if model_configs is None:
        model_configs = {}

    wf = Workflow()

    node_configs = [
        NodeConfig("requirement", agents["requirement"], _build_requirement_input, "requirement", output_format="md"),
        NodeConfig("testpoint", agents["testpoint"], _build_testpoint_input, "testpoint", output_format="md"),
        NodeConfig("aggregator", agents["aggregator"], _build_aggregator_input, "grouped_testpoints", output_format="md"),
        NodeConfig("testcase", agents["testcase"], _build_module_testcase_input, "testcase", output_format="md"),
        NodeConfig("review", agents["review"], _build_review_coverage_input, "review", output_format="md",
                   model_settings=model_configs.get("review", {}).get("settings")),
        NodeConfig("coverage", agents["coverage"], _build_review_coverage_input, "coverage", output_format="md",
                   model_settings=model_configs.get("coverage", {}).get("settings")),
        NodeConfig("gap", agents["gap"], _build_gap_input, "final_cases", GAP_SCHEMA, _gap_condition),
    ]

    for cfg in node_configs:
        wf.add_node(Node(
            name=cfg.name,
            agent=cfg.agent,
            input_fn=cfg.input_fn,
            output_key=cfg.output_key,
            schema=cfg.schema,
            condition=cfg.condition,
            model_settings=cfg.model_settings,
            output_format=cfg.output_format
        ))

    edges = [
        ("requirement", "testpoint"),
        ("testpoint", "aggregator"),
        ("aggregator", "testcase"),
        ("testcase", "review"),
        ("review", "coverage"),
        ("coverage", "gap"),
    ]

    for from_node, to_node in edges:
        wf.add_edge(from_node, to_node)

    return wf
```

- [ ] **Step 3: 更新 _build_review_coverage_input 使用 grouped_testpoints**

将 `_build_review_coverage_input` 函数替换为：

```python
def _build_review_coverage_input(ctx: Context) -> str:
    parts = []
    requirement = ctx.get("requirement", "")
    parts.append(f"## 需求信息\n{requirement}")

    grouped = ctx.get("grouped_testpoints", "")
    if grouped:
        parts.append(f"## 测试点\n{grouped}")
    else:
        testpoints = _get_testpoints_text(ctx)
        parts.append(f"## 测试点\n{testpoints}")

    cases = ctx.get("testcase")
    if cases:
        cases_text = cases if isinstance(cases, str) else json.dumps(cases, ensure_ascii=False)
        parts.append(f"## 测试用例\n{cases_text}")

    return "\n\n".join(parts)
```

- [ ] **Step 4: 验证语法**

Run: `cd /Users/lileilei/Desktop/AITestCraft && python3 -c "from core.workflow_builders import build_workflow; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add core/workflow_builders.py
git commit -m "feat: refactor workflow with module-aggregator node and grouped testpoints"
```

---

### Task 7: 修改 workflow.py 支持多模块并行提取

**Files:**
- Modify: `core/workflow.py`

- [ ] **Step 1: 在 Workflow 类中新增 run_parallel 方法**

在 `core/workflow.py` 的 `Workflow` 类中，在 `_get_execution_order` 方法之后添加：

```python
    async def run_parallel(self, node_name: str, ctx: Context, inputs: List[Dict[str, str]], output_key: str) -> Context:
        """
        并行执行同一节点多次（用于多模块测试点提取）
        
        Args:
            node_name: 要并行执行的节点名称
            ctx: 执行上下文
            inputs: 输入列表，每项包含 module_id 和 input
            output_key: 结果存储到上下文的键名
            
        Returns:
            执行后的上下文
        """
        node = self.nodes[node_name]
        task_id = ctx.get("task_id", "")
        
        if len(inputs) <= 1:
            single_input = inputs[0]["input"] if inputs else ""
            ctx.set(node.input_fn.__name__ + "_payload", single_input)
            ctx = await node.run(ctx)
            result = ctx.get(output_key, "")
            module_results = {inputs[0]["module_id"]: result} if inputs else {}
        else:
            logger.info(f"并行执行 [{node_name}]，模块数: {len(inputs)}")
            update_node_status(task_id, node_name, "running")
            
            ctx["token_stats"].ensure_node(node_name)
            
            tasks = []
            for item in inputs:
                temp_ctx = Context()
                temp_ctx.update(ctx)
                temp_ctx["task"] = item["input"]
                tasks.append((item["module_id"], node.agent, item["input"]))
            
            module_results = {}
            total_input_tokens = 0
            total_output_tokens = 0
            
            for module_id, agent, payload in tasks:
                try:
                    logger.info(f"并行执行 [{node_name}] 模块: {module_id}")
                    result = await run_with_retry(
                        agent, payload,
                        retries=node.max_retry,
                        timeout=node.timeout,
                        model_settings=node.model_settings
                    )
                    raw = result.text
                    if raw:
                        raw_str = str(raw).strip()
                        module_results[module_id] = raw_str
                        
                        usage = None
                        for attr_name in ["usage_details", "usage", "model_usage", "token_usage", "usage_info"]:
                            usage = getattr(result, attr_name, None)
                            if usage:
                                break
                        
                        if usage:
                            if hasattr(usage, '__dict__'):
                                usage_dict = vars(usage)
                            elif isinstance(usage, dict):
                                usage_dict = usage
                            else:
                                usage_dict = {}
                            
                            input_tokens = usage_dict.get("input_token_count", 0) or usage_dict.get("prompt_tokens", 0) or usage_dict.get("input_tokens", 0)
                            output_tokens = usage_dict.get("output_token_count", 0) or usage_dict.get("completion_tokens", 0) or usage_dict.get("output_tokens", 0)
                            total_input_tokens += input_tokens
                            total_output_tokens += output_tokens
                            
                            ctx["token_stats"].add(node_name, {
                                "input_token_count": input_tokens,
                                "output_token_count": output_tokens,
                                "total_token_count": input_tokens + output_tokens
                            })
                except Exception as e:
                    logger.error(f"并行执行 [{node_name}] 模块 {module_id} 失败: {e}")
                    module_results[module_id] = ""
            
            token_usage_data = None
            if total_input_tokens > 0 or total_output_tokens > 0:
                token_usage_data = {
                    "input": total_input_tokens,
                    "output": total_output_tokens,
                    "total": total_input_tokens + total_output_tokens
                }
            
            ctx.set("module_testpoints", module_results)
            update_node_status(task_id, node_name, "completed", {"output": module_results}, token_usage=token_usage_data)
            logger.info(f"并行执行 [{node_name}] 完成，模块数: {len(module_results)}")
        
        return ctx
```

- [ ] **Step 2: 在文件顶部添加 import**

在 `core/workflow.py` 的 import 区域添加：

```python
from core.retry import run_with_retry
from storage.repositories import update_node_status
```

- [ ] **Step 3: 验证语法**

Run: `cd /Users/lileilei/Desktop/AITestCraft && python3 -c "from core.workflow import Workflow; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add core/workflow.py
git commit -m "feat: add run_parallel method for multi-module testpoint extraction"
```

---

### Task 8: 修改 taskexecution.py 适配分块工作流

**Files:**
- Modify: `core/taskexecution.py`

- [ ] **Step 1: 修改 taskexecution 函数支持分块逻辑**

在 `core/taskexecution.py` 中，将 `taskexecution` 函数中工作流执行部分替换。找到 `try:` 块中的工作流执行代码，替换为：

```python
    try:
        logger.info(f"========== 工作流开始执行 ==========")
        
        # 先执行 requirement 节点
        if from_checkpoint:
            result_ctx = await wf.run_from_checkpoint("requirement", ctx)
        else:
            result_ctx = await wf.run("requirement", ctx)
        
        # 检查是否需要分块处理
        requirement_text = result_ctx.get("requirement", "")
        from core.workflow_builders import _parse_modules
        modules = _parse_modules(requirement_text)
        
        if len(modules) > Config.MODULE_SPLIT_THRESHOLD:
            logger.info(f"检测到 {len(modules)} 个模块，超过阈值 {Config.MODULE_SPLIT_THRESHOLD}，启用分块处理")
            
            # 并行提取各模块测试点
            from core.workflow_builders import _build_module_testpoint_inputs
            module_inputs = _build_module_testpoint_inputs(result_ctx)
            result_ctx = await wf.run_parallel("testpoint", result_ctx, module_inputs, "module_testpoints")
            
            # 继续执行后续节点
            remaining_nodes = ["aggregator", "testcase", "review", "coverage", "gap"]
            for node_name in remaining_nodes:
                node = wf.nodes[node_name]
                if node.condition and not node.condition(result_ctx):
                    logger.info(f"节点 [{node_name}] 跳过")
                    continue
                logger.info(f"节点开始: [{node_name}]")
                result_ctx = await node.run(result_ctx)
        else:
            logger.info(f"模块数 {len(modules)} 未超过阈值，使用标准流程")
        
        logger.info(f"========== 工作流执行完成 ==========")
```

- [ ] **Step 2: 验证语法**

Run: `cd /Users/lileilei/Desktop/AITestCraft && python3 -c "from core.taskexecution import taskexecution; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add core/taskexecution.py
git commit -m "feat: integrate module splitting into task execution flow"
```

---

### Task 9: 修改 formatters 支持按模块分组输出

**Files:**
- Modify: `formatters/markdown_formatter.py`
- Modify: `formatters/xmind_formatter.py`

- [ ] **Step 1: 修改 MarkdownFormatter 支持模块分组**

在 `formatters/markdown_formatter.py` 的 `format` 方法中，在 `priority_groups = self._group_by_priority(testcases)` 之前添加模块分组检测：

```python
        module_groups = self._group_by_module(testcases)
        if module_groups and len(module_groups) > 1:
            return self._format_by_module(testcases, meta, module_groups)
```

在类中新增方法：

```python
    def _group_by_module(self, testcases: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for case in testcases:
            module = case.get("module", "")
            if not module:
                return {}
            if module not in groups:
                groups[module] = []
            groups[module].append(case)
        return groups

    def _format_by_module(self, testcases: List[Dict[str, Any]], meta: Dict[str, Any], module_groups: Dict[str, List[Dict[str, Any]]]) -> str:
        lines = []
        lines.append("# 测试用例文档")
        lines.append("")
        lines.append("## 项目概述")
        lines.append(f"- **需求**: {meta['requirement'] or '未指定'}")
        lines.append(f"- **生成时间**: {meta['generated_at'] or datetime.now().strftime('%Y-%m-%d')}")
        lines.append(f"- **总计用例**: {len(testcases)} 条")
        lines.append(f"- **模块数**: {len(module_groups)}")
        lines.append("")

        for module_name, cases in module_groups.items():
            lines.append("---")
            lines.append("")
            lines.append(f"## 模块: {module_name}")
            lines.append("")
            priority_groups = self._group_by_priority(cases)
            for priority in ["P0", "P1", "P2"]:
                if priority not in priority_groups:
                    continue
                p_cases = priority_groups[priority]
                lines.append(f"### {priority} 优先级")
                lines.append("")
                lines.append(self._format_table(p_cases))
                lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## 用例统计")
        lines.append("")
        lines.append("| 模块 | 数量 |")
        lines.append("|------|------|")
        for module_name, cases in module_groups.items():
            lines.append(f"| {module_name} | {len(cases)} |")
        lines.append(f"| **总计** | **{len(testcases)}** |")

        return "\n".join(lines)
```

- [ ] **Step 2: 修改 XMindFormatter 支持模块分组**

在 `formatters/xmind_formatter.py` 的 `_build_content_json` 方法中，在 `priority_groups = self._group_by_priority(testcases)` 之前添加模块分组检测：

```python
        module_groups = self._group_by_module(testcases)
        if module_groups and len(module_groups) > 1:
            return self._build_content_by_module(testcases, meta, module_groups)
```

在类中新增方法：

```python
    def _group_by_module(self, testcases: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for case in testcases:
            module = case.get("module", "")
            if not module:
                return {}
            if module not in groups:
                groups[module] = []
            groups[module].append(case)
        return groups

    def _build_content_by_module(self, testcases: List[Dict[str, Any]], metadata: Dict[str, Any], module_groups: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        sheet_id = str(uuid.uuid4())
        root_id = str(uuid.uuid4())

        children = []
        for module_name, cases in module_groups.items():
            module_node = self._build_module_node(module_name, cases)
            children.append(module_node)

        summary_node = self._build_summary_node(testcases, metadata)
        children.append(summary_node)

        sheet = {
            "id": sheet_id,
            "class": "sheet",
            "title": metadata.get("title", "测试用例文档"),
            "rootTopic": {
                "id": root_id,
                "class": "topic",
                "title": metadata.get("requirement", "测试用例"),
                "structureClass": "org.xmind.ui.map.clockwise",
                "children": {
                    "attached": children
                }
            }
        }

        return [sheet]

    def _build_module_node(self, module_name: str, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        module_id = str(uuid.uuid4())
        priority_groups = self._group_by_priority(cases)

        children = []
        for priority in ["P0", "P1", "P2"]:
            if priority not in priority_groups:
                continue
            p_cases = priority_groups[priority]
            priority_node = self._build_priority_node(priority, p_cases)
            children.append(priority_node)

        return {
            "id": module_id,
            "class": "topic",
            "title": module_name,
            "children": {
                "attached": children
            }
        }
```

- [ ] **Step 3: 验证语法**

Run: `cd /Users/lileilei/Desktop/AITestCraft && python3 -c "from formatters import MarkdownFormatter, XMindFormatter; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add formatters/markdown_formatter.py formatters/xmind_formatter.py
git commit -m "feat: add module-grouped output for markdown and xmind formatters"
```

---

### Task 10: 端到端测试验证

**Files:**
- No new files

- [ ] **Step 1: 启动服务**

Run: `cd /Users/lileilei/Desktop/AITestCraft && python3 -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload`

- [ ] **Step 2: 提交小需求测试（验证向后兼容）**

Run:
```bash
curl -X POST http://localhost:8001/api/tasks/run \
  -F "task=手机号验证码登录，验证码6位数字，有效期5分钟"
```

Expected: 返回 task_id，任务执行成功

- [ ] **Step 3: 提交大需求测试（验证分块处理）**

Run:
```bash
curl -X POST http://localhost:8001/api/tasks/run \
  -F "task=电商系统需求：1.用户注册：手机号注册，验证码6位，密码8-20位含字母数字。2.用户登录：支持手机号验证码登录和密码登录，登录失败5次锁定30分钟。3.商品搜索：支持关键词搜索、分类筛选、价格排序，搜索结果分页每页20条。4.购物车：添加商品、修改数量、删除商品、选择结算。5.订单管理：创建订单、取消订单（30分钟内）、查看订单列表、订单详情。6.支付：支持微信支付和支付宝，支付超时15分钟自动取消。7.退款：申请退款、审核退款、退款到账。"
```

Expected: 返回 task_id，任务执行成功，结果按模块分组

- [ ] **Step 4: 验证结果格式**

查询结果，检查是否按模块分组输出。

- [ ] **Step 5: Final Commit**

```bash
git add -A
git commit -m "feat: complete large-requirement module splitting implementation"
```
