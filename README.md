# Arcadegent

Arcadegent 是一个面向街机门店检索与问答的 Agent 应用，当前已完成 W1-W4 MVP 闭环：

- ETL 入仓：坏行容错、QA 报告、批次追踪、可选 SQLite 落盘
- FastAPI 服务：门店检索、详情、地区级联、Chat、SSE 流式事件
- React 前端：检索页、详情展示、地区联动筛选
- 测试基线：ETL + API 单元/集成测试

## 环境要求

- Python `>=3.11`
- Node.js `>=18`
- npm `>=9`

## 快速启动

以下命令默认在项目根目录 `Arcadegent/` 执行。

### 1) 安装依赖

```bash
# 后端（含测试依赖）
cd agent
python -m pip install -e ".[dev]"

# 前端
cd ../apps/web
npm install
cd ../..
```

### 2) 启动后端 API

PowerShell:

```powershell
cd agent
$env:ARCADE_DATA_JSONL = "..\data\raw\bemanicn\shops_detail.jsonl"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --access-log
```

接口入口：

- Health: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`

### 3) 启动前端

```powershell
cd apps/web
$env:VITE_API_BASE = "http://localhost:8000"
npm run dev
```

打开：`http://localhost:5173`

## ETL 数据处理（可选但推荐）

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

## 常用开发命令

```bash
# 项目测试（根目录）
python -m pytest -q

# 仅后端测试
python -m pytest -q agent/app/tests

# 仅 ETL 测试
python -m pytest -q scripts/etl/tests

# 前端打包
cd apps/web && npm run build
```

## 关键环境变量

- `ARCADE_DATA_JSONL`: 后端读取的数据源 JSONL 路径
- `VITE_API_BASE`: 前端 API 地址（默认 `http://localhost:8000`）
- `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`: LLM Provider 配置（OpenAI 兼容）
- `AMAP_API_KEY` / `AMAP_BASE_URL`: 高德路线能力配置

## 项目结构

```text
agent/                FastAPI 后端与 Agent 运行时
apps/web/             React + Vite 前端
scripts/etl/          ETL 脚本与测试
data/raw/             原始数据
data/processed/       ETL 产物
supabase/migrations/  数据库迁移脚本
docs/                 计划、说明与测试文档
```

## 相关文档

- `docs/plans/人工测试清单.md`
- `docs/plans/W1-W4开发落地记录.md`
- `docs/plans/2026Q1-5周技术开发实施方案.md`
- `scripts/etl/README.md`
