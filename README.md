# Arcadegent

Arcadegent 是一个面向机厅检索、问答和路线建议的 Agent 应用。当前仓库包含 FastAPI 后端、React + Vite 前端、Bemanicn 抓取与 ETL 脚本，以及一套基于本地 JSONL 的查询与会话运行时。

## 当前能力

- Agent 对话：支持检索、附近推荐、路线规划三类意图，并通过 SSE 推送阶段切换、工具执行和回复流。
- 机厅检索：支持关键词搜索、地区级联筛选、机种数量排序和门店详情查看。
- 会话管理：支持历史会话列表、单会话详情和删除。
- 数据处理：提供抓取脚本、ETL 规范化脚本和 QA 产物输出。

## 技术栈

- Backend: Python 3.11+, FastAPI, Pydantic
- Frontend: React 18, TypeScript, Vite
- Data: 本地 JSONL 读模型，附带 ETL 产物与 Supabase migration 草案
- Integration: OpenAI-compatible LLM provider，高德路线 API（不可用时自动退化为离线估算）

## 目录结构

```text
backend/              FastAPI 后端与 Agent 运行时
apps/web/             React + Vite 前端
scripts/              数据抓取与辅助脚本
scripts/etl/          ETL 脚本与测试
data/raw/             原始数据
data/processed/       ETL 产物
supabase/migrations/  数据库迁移草案
docs/                 计划、交接和开发说明
```

## 环境要求

- Python `>=3.11`
- Node.js `>=18`
- npm `>=9`

## 快速启动

以下命令默认在仓库根目录 `Arcadegent/` 执行。

### 1. 安装依赖

```powershell
cd backend
python -m pip install -e ".[dev]"

cd ..\apps\web
npm install

cd ..\..
```

### 2. 配置环境变量

后端启动时会自动读取根目录 `.env`。一个最小示例如下：

```dotenv
APP_ENV=dev
ARCADE_DATA_JSONL=data/raw/bemanicn/shops_detail.jsonl
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
AMAP_API_KEY=
AMAP_BASE_URL=https://restapi.amap.com
```

说明：

- `ARCADE_DATA_JSONL` 是后端实际读取的数据源，默认指向 `data/raw/bemanicn/shops_detail.jsonl`。
- 未配置 `LLM_API_KEY` 时服务仍可启动，但 Agent 对话会明显退化，联调前建议配置。
- 未配置 `AMAP_API_KEY` 时，路线规划会返回离线估算结果而不是高德实算路线。
- `VITE_API_BASE` 属于前端环境变量，建议在启动前端时显式设置，或写入 `apps/web/.env.local`。

### 3. 启动后端 API

```powershell
cd backend
$env:ARCADE_DATA_JSONL = "..\data\raw\bemanicn\shops_detail.jsonl"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --access-log
```

接口入口：

- Health: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`

### 4. 启动前端

```powershell
cd apps/web
$env:VITE_API_BASE = "http://localhost:8000"
npm run dev
```

打开：`http://localhost:5173`

## 接口概览

- `GET /health`：健康检查与数据加载状态
- `GET /api/v1/arcades`：机厅列表、筛选、排序
- `GET /api/v1/arcades/{source_id}`：机厅详情
- `GET /api/v1/regions/provinces`：省份列表
- `GET /api/v1/regions/cities`：城市列表
- `GET /api/v1/regions/counties`：区县列表
- `POST /api/chat`：Agent 对话入口
- `GET /api/v1/chat/sessions`：会话列表
- `GET /api/v1/chat/sessions/{session_id}`：会话详情
- `DELETE /api/v1/chat/sessions/{session_id}`：删除会话
- `GET /api/stream/{session_id}`：SSE 实时事件流

## 数据处理

如果需要把原始 JSONL 规范化并生成 QA 产物，可以执行：

```bash
python scripts/etl/ingest_arcades.py \
  --input data/raw/bemanicn/shops_detail.jsonl \
  --run-summary data/raw/bemanicn/run_summary.json \
  --output-dir data/processed/bemanicn \
  --sqlite-path data/processed/arcadegent.db
```

主要产物：

- `data/processed/bemanicn/arcade_shops.jsonl`
- `data/processed/bemanicn/arcade_titles.jsonl`
- `data/processed/bemanicn/bad_rows.jsonl`
- `data/processed/bemanicn/qa_report.json`
- `data/processed/bemanicn/ingest_run.json`

说明：

- 当前本地 API 默认直接读取 `ARCADE_DATA_JSONL` 指向的 JSONL 文件。
- ETL 的主要价值是做规范化、质量校验和中间产物沉淀，不是当前 API 的唯一前置步骤。

## 常用开发命令

后端测试：

```powershell
cd backend
python -m pytest -q
```

ETL 测试：

```powershell
python -m pytest -q scripts/etl/tests
```

前端打包：

```powershell
cd apps/web
npm run build
```

## 当前限制

- 聊天会话当前保存在后端内存中，服务重启后历史会话会丢失。
- 机厅查询目前使用本地 JSONL 读模型，不是数据库在线查询。
- 路线规划在没有高德 API Key 或外部请求失败时会退化为离线估算。

