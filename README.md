# TEvox-ai

TEvox-ai 是一个基于 AI 的代码智能助手项目，集成了代码分析、知识图谱构建、强化学习训练等核心功能，为开发者提供智能化的代码辅助能力。

## 项目结构

```
TEvox-ai/
├── benchmark-data/     # 基准测试数据集和结果
├── TEvox-client/       # VS Code 扩展客户端
├── TEvox-server/       # 后端服务
└── .gitignore          # Git 忽略配置
```

---

## 文件夹说明

### 1. benchmark-data

**作用**: 存放基准测试数据集和结果，用于评估和验证代码分析、修复等功能的性能指标。

### 2. TEvox-client

**作用**: VS Code 扩展客户端，提供 IDE 集成界面，支持代码聊天、任务管理、智能调试等功能。

**目录结构**:
```
TEvox-client/
├── media/              # 静态资源（图标、HTML页面、聊天界面）
├── src/
│   ├── api/            # API 接口定义（调试器、终端、工作区等）
│   ├── tools/          # 工具函数实现
│   ├── web/            # Web 视图组件（聊天视图、任务管理器）
│   ├── backend_server.ts  # 后端服务连接管理
│   └── extension.ts    # VS Code 扩展入口文件
└── webview-ui/         # React 前端界面（使用 Vite 构建）
```

### 3. TEvox-server

**作用**: 后端核心服务，包含 RAG（检索增强生成）、智能 Agent等模块。

**目录结构**:
```
TEvox-server/
── src/
    ├── base/           # 基础类和接口（Action、Config、Task、Tool）
    ├── core/
    │   ├── agents/     # 核心 Agent 实现（Executor、Generator、Planner、Reviewer）
    │   ├── rag/        # RAG 模块（代码分析、知识图谱构建与检索）
    │   └── tools/      # 工具定义（搜索、Web 搜索、经验学习）
    ├── serve/          # 服务启动入口
    └── utils/          # 通用工具（LLM 封装、日志、向量数据库）
```

### 3.1 RAG Code 模块详解

`TEvox-server/src/core/rag/code` 是项目的核心模块，专注于代码分析、知识图谱构建和智能代码辅助功能。

**目录结构**:
```
code/
├── agents/             # 代码分析 Agent 集合
│   ├── base_agent.py          # 基础 Agent 类
│   ├── code_completer.py      # 代码补全 Agent
│   ├── debugger.py            # 代码调试 Agent
│   ├── evaluator.py           # 代码评估 Agent
│   ├── graph_extractor.py     # 知识图谱提取 Agent
│   ├── grapher.py             # 图谱构建器
│   └── knowledge_extractor.py # 知识提取 Agent
├── context/            # 上下文分析模块
│   ├── fileanalyze.py         # 文件级别分析
│   ├── folderanalyze.py       # 文件夹级别分析
│   └── symbols.py             # 符号提取与分析
├── index/              # 索引构建模块
│   ├── autoencoder/           # 自动编码器索引
│   ├── baseline/              # 基线提取器
│   ├── designer/              # 设计模式分析
│   ├── function_graph/        # 函数调用图构建
│   ├── linked_graph/          # 链接图谱管理
│   ├── similarity/            # 代码相似度分析
│   └── config.py              # 索引配置
├── query/              # 查询与检索模块
│   ├── evaluator/             # 代码质量评估
│   ├── generator/             # 代码生成
│   ├── retriever/             # 代码检索器
│   └── graphml_query_engine.py # 图谱查询引擎
├── repair/             # 代码修复模块
│   ├── repairer.py            # 代码修复器
│   └── repairer_prompt.py     # 修复提示词模板
├── storage/            # 存储管理
│   └── graph_json_manager.py  # 图谱 JSON 存储管理
├── tools/              # 工具模块
│   ├── file_operation_tool.py # 文件操作工具
│   ├── graph_tool.py          # 图谱操作工具
│   ├── knowledge_tool.py      # 知识查询工具
│   ├── terminal_tool.py       # 终端操作工具
│   └── vscode.py              # VS Code 集成工具
├── workflow.py         # 工作流管理
└── run_pipeline.py     # 管道执行入口
```

**核心功能说明**:

| 子模块 | 功能描述 |
|--------|----------|
| **agents** | 提供多种代码分析 Agent，包括代码补全、调试、评估、知识提取等 |
| **context** | 分析代码上下文，提取文件结构、文件夹依赖和符号信息 |
| **index** | 构建代码索引，支持函数调用图、相似度分析、设计模式识别 |
| **query** | 提供代码检索、生成和质量评估能力 |
| **repair** | AI 驱动的代码修复，自动识别并修复代码问题 |
| **tools** | 封装文件操作、终端命令、VS Code 集成等工具能力 |

**主要工作流**:
1. **代码索引构建**: 通过 `index/` 模块分析代码库，构建知识图谱
2. **代码检索**: 通过 `query/retriever` 在图谱中检索相关代码
3. **代码分析**: 通过 `agents/` 模块进行代码理解和分析
4. **代码修复**: 通过 `repair/` 模块进行智能代码修复

---

## 运行方式

### 前置要求

- Python 3.10+
- Node.js 18+
- VS Code（用于开发扩展）

### 运行 TEvox-client（VS Code 扩展）

```bash
cd TEvox-client

# 安装依赖
npm install

# 开发模式构建（自动监听变化）
npm run watch

# 生产模式构建
npm run compile

# 在 VS Code 中调试扩展（按 F5）
```

### 运行 TEvox-server（后端服务）

```bash
cd TEvox-server

# 安装依赖（推荐使用虚拟环境）
pip install -r requirements.txt

```

---

## 核心功能

### 1. 代码分析模块 (`agents/`)

| 文件 | 功能描述 | 运行方式 |
|------|----------|----------|
| `base_agent.py` | 基础 Agent 类，提供通用的 Agent 接口和方法 | 作为基类被其他 Agent 继承使用 |
| `code_completer.py` | 代码补全 Agent，基于上下文生成代码补全建议 | `from agents.code_completer import CodeCompleter` |
| `debugger.py` | 代码调试 Agent，分析代码错误并提供修复方案 | `from agents.debugger import DebuggerAgent` |
| `evaluator.py` | 代码评估 Agent，评估代码质量、可读性和安全性 | `from agents.evaluator import CodeEvaluator` |
| `graph_extractor.py` | 知识图谱提取 Agent，从代码中提取实体和关系 | `from agents.graph_extractor import GraphExtractor` |
| `grapher.py` | 图谱构建器，构建代码知识图谱 | `from agents.grapher import CodeGrapher` |
| `knowledge_extractor.py` | 知识提取 Agent，提取代码中的业务知识 | `from agents.knowledge_extractor import KnowledgeExtractor` |

### 2. 上下文分析模块 (`context/`)

| 文件 | 功能描述 | 运行方式 |
|------|----------|----------|
| `fileanalyze.py` | 文件级别分析，提取文件结构和依赖关系 | `python -m context.fileanalyze --file <file_path>` |
| `folderanalyze.py` | 文件夹级别分析，分析项目结构和模块依赖 | `python -m context.folderanalyze --dir <dir_path>` |
| `symbols.py` | 符号提取与分析，识别变量、函数、类等符号 | `from context.symbols import SymbolExtractor` |

### 3. 索引构建模块 (`index/`)

| 文件/子模块 | 功能描述 | 运行方式 |
|-------------|----------|----------|
| `autoencoder/` | 基于自动编码器的代码索引 | `python -m index.autoencoder.encode --input <code_dir>` |
| `baseline/` | 基线代码提取器 | `python -m index.baseline.extractor --src <source_dir>` |
| `designer/` | 设计模式分析器，识别代码中的设计模式 | `python -m index.designer.designer --file <file_path>` |
| `function_graph/` | 函数调用图构建 | `python -m index.function_graph.find_all_files --dir <project_dir>` |
| `similarity/` | 代码相似度分析 | `python -m index.similarity.compute_function_text_similarities --dir <code_dir>` |
| `linked_graph/` | 链接图谱管理 | `python -m index.linked_graph.read_linked_graph --file <graph_file>` |

### 4. 查询与检索模块 (`query/`)

| 文件/子模块 | 功能描述 | 运行方式 |
|-------------|----------|----------|
| `evaluator/` | 代码质量评估工具集 | `python -m query.evaluator.evaluator --file <code_file>` |
| `generator/` | 代码生成模块 | `python -m query.generator.github_issues_downloader --repo <repo_url>` |
| `retriever/` | 代码检索器，基于知识图谱检索相关代码 | `from query.retriever.retriever import CodeRetriever` |
| `graphml_query_engine.py` | GraphML 格式图谱查询引擎 | `from query.graphml_query_engine import GraphQueryEngine` |

### 5. 代码修复模块 (`repair/`)

| 文件 | 功能描述 | 运行方式 |
|------|----------|----------|
| `repairer.py` | 代码修复器，自动识别并修复代码问题 | `from repair.repairer import CodeRepairer` |
| `repairer_prompt.py` | 修复提示词模板定义 | 作为 repairer 的依赖模块使用 |

### 6. 工具模块 (`tools/`)

| 文件 | 功能描述 | 运行方式 |
|------|----------|----------|
| `file_operation_tool.py` | 文件操作工具（读写、复制、删除等） | `from tools.file_operation_tool import FileOperationTool` |
| `graph_tool.py` | 图谱操作工具（节点、边的增删改查） | `from tools.graph_tool import GraphTool` |
| `knowledge_tool.py` | 知识查询工具 | `from tools.knowledge_tool import KnowledgeTool` |
| `terminal_tool.py` | 终端操作工具 | `from tools.terminal_tool import TerminalTool` |
| `vscode.py` | VS Code 集成工具 | `from tools.vscode import VSCodeTool` |

### 7. 工作流与管道 (`workflow.py`, `run_pipeline.py`)

| 文件 | 功能描述 | 运行方式 |
|------|----------|----------|
| `workflow.py` | 工作流管理，定义代码分析流程 | `from workflow import CodeAnalysisWorkflow` |
| `run_pipeline.py` | 管道执行入口，执行完整的代码分析流程 | `python run_pipeline.py --config <config.yaml>` |

---

## 技术栈

| 类别 | 技术 |
|------|------|
| **前端** | React + TypeScript + Vite |
| **后端** | Python + FastAPI |
| **数据库** | LanceDB（向量数据库） |
| **IDE 集成** | VS Code Extension API |

---

## 许可证

本项目采用 MIT 许可证。

---

**注意**: 在运行前请确保已配置好环境变量，特别是 API Key 和数据库连接信息。敏感配置请使用环境变量或配置文件管理，不要硬编码到代码中。