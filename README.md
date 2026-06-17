# Agent Coding Assistant

一个多 Agent CLI 编程助手，通过模拟虚拟开发团队（PM → 架构师 → 程序员 → 审查员 → 测试员）帮助独立开发者完成从需求到测试的完整软件开发生命周期。

## 架构概览

```
用户请求
   │
   ▼
┌──────────────┐     ┌───────────────────────────────────────────────┐
│ Orchestrator │────▶│           Pipeline (串行执行引擎)              │
│  意图解析     │     │                                               │
└──────────────┘     │  📋 PM ──▶ 🏗️ Architect ──▶ 💻 Coder         │
                     │                           ▲    │    │          │
                     │                           │    ▼    │          │
                     │                           │  🔍 Reviewer       │
                     │                           │    │               │
                     │                           └────┘  Coder↔Reviewer 反馈循环
                     │                                │               │
                     │                                ▼               │
                     │                          🧪 Tester             │
                     │                           ▲    │               │
                     │                           └────┘  Coder↔Tester 反馈循环
                     └───────────────────────────────────────────────┘
```

每个 Agent 产出一个结构化 Artifact（JSON 数据 + 人类可读摘要），作为下一个 Agent 的输入。

## 安装

```bash
# 克隆项目
git clone git@github.com:Go-Hub-l/agent-coding-assistant.git
cd agent-coding-assistant

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # macOS/Linux

# 安装（可编辑模式）
pip install -e .
```

## 配置

将 `.env.example` 复制为 `.env` 并填入 API 密钥：

```bash
cp .env.example .env
```

`.env` 支持的配置项：

```env
# 必填：DeepSeek API 密钥
DEEPSEEK_API_KEY=sk-xxx

# 可选：API 地址（默认 https://api.deepseek.com）
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 可选：为每个 Agent 单独指定模型（默认 deepseek-chat）
ORCHESTRATOR_MODEL=deepseek-chat
PM_MODEL=deepseek-chat
ARCHITECT_MODEL=deepseek-chat
CODER_MODEL=deepseek-chat
REVIEWER_MODEL=deepseek-chat
TESTER_MODEL=deepseek-chat

# 可选：反馈循环最大重试次数（默认 3）
MAX_FEEDBACK_RETRIES=3
```

模型选择通过 `.env` 文件配置；System Prompt 和工具权限通过代码内常量配置。

## 使用方式

### 基本用法 — 从零开始建项目（Greenfield 模式）

```bash
agent-assist build "实现一个 REST API 的用户注册和登录功能，使用 FastAPI + PostgreSQL"
```

Pipeline 流程：

1. **意图解析** — Orchestrator 将自然语言请求解析为结构化意图文档，等待用户确认或修正
2. **PM 阶段** — 生成用户故事、验收标准、依赖关系
3. **架构师阶段** — 产出模块划分、接口定义、技术选型
4. **程序员阶段** — 根据架构设计生成代码文件
5. **审查员阶段** — 审查代码质量，发现问题时触发 Coder↔Reviewer 反馈循环
6. **测试员阶段** — 生成测试套件，测试失败时触发 Coder↔Tester 反馈循环

### 迭代已有项目（Iteration 模式）

指定 `--project-dir` 指向已有项目目录，系统会自动扫描文件结构、依赖关系和代码符号，生成项目上下文摘要注入到所有 Agent 的 prompt 中：

```bash
agent-assist build "给现有项目添加 JWT token 刷新机制" --project-dir /path/to/my-project
```

### 人工介入检查点（Intervention）

使用 `--intervene` 在每个阶段完成后暂停，展示 Artifact 供人工审查：

```bash
agent-assist build "实现 WebSocket 实时通知系统" --intervene
```

在每个检查点可以选择：

- **approve** — 通过，继续下一阶段
- **modify** — 修改 Artifact 后继续
- **abort** — 终止 Pipeline

也可以只在特定阶段暂停：

```bash
agent-assist build "重构数据库查询层" --intervene-at pm,architect
```

### 指定 .env 文件

```bash
agent-assist build "..." --env-file /path/to/.env
```

## Pipeline 机制

### 反馈循环

Pipeline 内置两个局部反馈循环：

- **Coder ↔ Reviewer** — Reviewer 发现 major/critical 问题时，将问题反馈给 Coder 修复后重新审查，直到通过或达到最大重试次数
- **Coder ↔ Tester** — Tester 测试失败时，将失败详情反馈给 Coder 修复后重新测试

两种反馈循环都受 `MAX_FEEDBACK_RETRIES` 配置限制。重试耗尽后 Pipeline 进入 escalated 状态，交由用户决策。

### 退出码

| 退出码 | 含义 |
|--------|------|
| `0` | Pipeline 成功完成 |
| `1` | 用户主动中止（abort） |
| `2` | 错误或升级（API 错误、重试耗尽、架构级问题） |

### Artifact 验证

每个 Agent 的输出在传递到下一个 Agent 之前会经过 schema 验证，确保结构完整（如 PM 产出必须包含 `user_stories`，Coder 产出必须包含 `files`）。

## 开发

```bash
# 运行测试
python -m pytest -v

# 带覆盖率
python -m pytest --cov=agent_assistant --cov-report=term-missing
```

## 项目结构

```
src/agent_assistant/
├── cli.py                  # CLI 入口（Typer）
├── config.py               # 配置加载（.env → dataclass）
├── agents/                 # 五个角色 Agent
│   ├── pm.py               #   需求分析
│   ├── architect.py        #   架构设计
│   ├── coder.py            #   代码实现
│   ├── reviewer.py         #   代码审查
│   └── tester.py           #   测试生成
├── llm/
│   └── client.py           # OpenAI 兼容 API 客户端（httpx）
├── orchestrator/
│   └── intent.py           # 意图解析与修正
├── pipeline/
│   ├── agent.py            # Agent 基类与角色枚举
│   ├── artifact.py         # Artifact 数据结构
│   ├── context.py          # AgentContext（传递给每个 Agent 的上下文）
│   ├── intervention.py     # 介入系统（检查点暂停/审批/修改）
│   ├── pipeline.py         # 串行执行引擎 + 反馈循环
│   ├── session.py          # Session 状态跟踪
│   └── validation.py       # Artifact schema 验证
├── project_context/
│   ├── scanner.py          # 项目规则扫描（文件树、依赖、AST）
│   └── summarizer.py       # LLM 语义摘要
└── tools/
    ├── base.py             # 工具基类与注册表
    ├── file_tools.py       # 文件读写、目录列表、测试执行
    └── permissions.py      # 角色-工具权限映射
```

## License

MIT
