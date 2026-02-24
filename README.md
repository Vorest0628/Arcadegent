# Arcadegent

Arcadegent 是面向街机门店检索的 Agent 化项目，当前已完成 W1-W4 的 MVP 版本：

- 数据入仓 ETL（坏行容错 + QA 报告 + 批次追踪）
- FastAPI 查询/会话接口（含 SSE）
- React 检索与详情页
- Supabase 首版迁移脚本
- 单测/集成测试基线

## 快速启动

### 1) 跑 ETL

```bash
python scripts/etl/ingest_arcades.py \
  --input data/raw/bemanicn/shops_detail.jsonl \
  --run-summary data/raw/bemanicn/run_summary.json \
  --output-dir data/processed/bemanicn \
  --sqlite-path data/processed/arcadegent.db
```

### 2) 启动后端

```bash
cd agent
python -m pip install -e .
set ARCADE_DATA_JSONL=../data/raw/bemanicn/shops_detail.jsonl
uvicorn app.main:app --reload --port 8000
```

可选环境变量（提供真实能力）：

- `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`（OpenAI 兼容 `chat/completions`）
- `AMAP_API_KEY`, `AMAP_BASE_URL`（高德 WebService 路线）

### 3) 启动前端

```bash
cd apps/web
npm install
npm run dev
```

更多验收步骤见：`docs/plans/人工测试清单.md`
