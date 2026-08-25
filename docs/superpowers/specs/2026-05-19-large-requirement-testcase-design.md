# 大需求分块处理测试用例生成方案

**日期**: 2026-05-19
**状态**: Approved

---

## 1. 背景与目标

### 1.1 问题描述

当前 7 节点工作流在处理大需求时存在用例遗漏问题：

```
requirement → testpoint → dedup → testcase → review → coverage → gap
```

**根本原因**：
- LLM 上下文窗口有限，大需求一次性处理超出限制
- testpoint-extractor 一次性提取所有测试点，中间内容被截断
- 遗漏在测试点提取阶段已发生，后续 gap-filler 无法完全补救

### 1.2 优化目标

- 将大需求按模块拆分为多个子任务，并行提取测试点
- 全局合并去重，保证不遗漏
- 保持向后兼容，小需求仍走原有流程

---

## 2. 设计方案

### 2.1 整体架构

```
┌─────────────┐
│ requirement │  ──► [需求解析 + 模块拆分]
└─────────────┘                │
                               ▼
                    ┌──────────────────────┐
                    │   模块列表 (按优先级)  │
                    │  [模块1, 模块2, ...]  │
                    └──────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
    ┌───────────┐        ┌───────────┐        ┌───────────┐
    │ testpoint │        │ testpoint │   ...  │ testpoint │
    │  模块1    │        │  模块2    │        │  模块N    │
    └───────────┘        └───────────┘        └───────────┘
          │                    │                    │
          └────────────────────┼────────────────────┘
                               ▼
                    ┌──────────────────────┐
                    │  模块汇总 (aggregator) │
                    │   - 合并去重          │
                    │   - 保留模块归属      │
                    │   - 按模块分组输出    │
                    └──────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │      testcase        │
                    │  按模块逐个生成用例   │
                    │  输出按模块分组       │
                    └──────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  review → coverage → gap │
                    └──────────────────────┘
```

### 2.2 节点变更

#### 2.2.1 requirement-parser（增强）

**输入**: 原始需求文本

**输出**:
```json
{
  "requirement": "完整需求描述（可选，保留兼容）",
  "modules": [
    {
      "id": "M1",
      "name": "用户登录",
      "priority": "P0",
      "content": "登录模块的完整需求描述..."
    },
    {
      "id": "M2",
      "name": "商品浏览",
      "priority": "P1",
      "content": "商品浏览模块的需求描述..."
    }
  ]
}
```

**拆分策略**:
- 先拆分再处理：LLM 先识别模块并排序，再进入下一阶段
- 拆分维度：按功能模块 / 业务流程 / 页面/接口
- 模块数量阈值：`MAX_MODULES_BEFORE_SPLIT`（默认 3）
  - 模块数 ≤ 阈值：退化为单模块，走原有流程
  - 模块数 > 阈值：触发分块处理

#### 2.2.2 testpoint-extractor（增强）

**输入**: 模块化需求（单个或多个模块）

**行为**:
- 单模块模式：小需求，直接提取测试点（现有逻辑）
- 多模块模式：接收模块列表，并行提取各模块测试点

**输出**: 按模块独立的测试点列表
```json
{
  "module_testpoints": {
    "M1": [
      {"id": "TP001-M1", "module": "M1", "type": "functional", "point": "...", "priority": "P0"},
      ...
    ],
    "M2": [
      {"id": "TP001-M2", "module": "M2", "type": "functional", "point": "...", "priority": "P1"},
      ...
    ]
  }
}
```

**并行执行**: 使用 `asyncio.gather` 并行调用 LLM

#### 2.2.3 module-aggregator（新增节点）

**输入**: 各模块测试点列表

**处理逻辑**:
1. 合并所有模块测试点
2. 全局去重（语义去重，参考 testpoint-deduplicator 逻辑）
3. **保留模块归属**：去重后的测试点仍携带 `module` 字段
4. 全局优先级排序（P0 > P1 > P2）
5. 重新编号（TP001, TP002, ...）
6. **按模块分组输出**：最终结果按模块组织

**输出**:
```json
{
  "testpoints": [
    {"id": "TP001", "module": "M1", "type": "functional", "point": "...", "priority": "P0"},
    {"id": "TP002", "module": "M1", "type": "boundary", "point": "...", "priority": "P0"},
    ...
  ],
  "grouped_testpoints": {
    "M1": {
      "name": "用户登录",
      "priority": "P0",
      "testpoints": [
        {"id": "TP001", "module": "M1", "type": "functional", "point": "...", "priority": "P0"},
        ...
      ]
    },
    "M2": {
      "name": "商品浏览",
      "priority": "P1",
      "testpoints": [
        {"id": "TP005", "module": "M2", "type": "functional", "point": "...", "priority": "P1"},
        ...
      ]
    }
  },
  "dedup_count": 5,
  "total_count": 30,
  "module_summary": {"M1": 15, "M2": 10}
}
```

**与现有 dedup 节点关系**: module-aggregator 承担原 dedup 职责，可选择复用或替换

#### 2.2.4 testcase-generator（增强）

**输入**: 按模块分组的测试点（`grouped_testpoints`）

**行为**:
- **按模块逐个生成用例**：每个模块独立生成测试用例
- 模块内按优先级排序（P0 > P1 > P2）
- 输出按模块分组，每个模块下包含该模块的全部用例

**输出**:
```json
{
  "testcases": [
    {
      "module": "M1",
      "module_name": "用户登录",
      "module_priority": "P0",
      "cases": [
        {"id": "TC001", "name": "Login-Correct", "priority": "P0", ...},
        {"id": "TC002", "name": "Login-Wrong", "priority": "P1", ...},
        ...
      ]
    },
    {
      "module": "M2",
      "module_name": "商品浏览",
      "module_priority": "P1",
      "cases": [
        {"id": "TC010", "name": "Browse-ProductList", "priority": "P1", ...},
        ...
      ]
    }
  ],
  "total_count": 25,
  "module_summary": {"M1": 12, "M2": 13}
}
```

**最终输出格式（Markdown/Excel/XMind）**:
- 按模块分章节/分组展示
- 每个模块下按优先级排序
- 模块之间按模块优先级排序

---

## 3. 兼容性设计

### 3.1 小需求兼容

当 `modules.length <= MAX_MODULES_BEFORE_SPLIT` 时：
- requirement-parser 输出 `modules.length == 1`
- testpoint-extractor 检测到单模块，退化为现有流程
- module-aggregator 检测到单模块，直接透传

### 3.2 节点配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `MAX_MODULES_BEFORE_SPLIT` | 3 | 超过此阈值触发分块 |
| `MAX_MODULE_TOKENS` | 4000 | 单模块最大 token 数 |

---

## 4. 实现计划

### 4.1 文件变更

| 文件 | 变更类型 |
|------|----------|
| `skills/requirement-parser/SKILL.md` | 修改：增加模块拆分输出 |
| `skills/testpoint-extractor/SKILL.md` | 修改：支持多模块并行 |
| `skills/testpoint-deduplicator/SKILL.md` | 或可废弃：功能合并到 aggregator |
| `core/workflow.py` | 修改：增加 aggregator 节点 |
| `core/workflow_builders.py` | 修改：适配新的数据流 |
| `config/config.py` | 新增：分块相关配置 |

### 4.2 新增文件

| 文件 | 说明 |
|------|------|
| `skills/module-aggregator/SKILL.md` | 模块汇总节点技能定义 |
| `core/nodes/module_aggregator.py` | 模块汇总节点实现 |

### 4.3 执行顺序

1. 修改 requirement-parser SKILL.md
2. 修改 testpoint-extractor SKILL.md
3. 新增 module-aggregator SKILL.md
4. 新增 module_aggregator.py 节点实现
5. 修改 workflow_builders.py 接入新节点
6. 修改 config.py 增加配置项
7. 测试验证

---

## 5. 风险与 Mitigation

| 风险 |  Mitigation |
|------|-------------|
| 模块拆分质量不稳定 | prompt 优化 + 人工审核示例 |
| 并行执行 token 消耗翻倍 | 配置阈值控制触发条件 |
| 全局优先级排序丢失模块内聚性 | 保留 module 字段，方便后续分析 |
