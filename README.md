# AITravel / ChinaTravel Planner

AITravel 是一个本地可运行的中国旅行规划应用：前端用 Vue 3 提供对话式旅行需求澄清、规划清单确认、历史行程、版本时间线和表单化二次编辑；后端用 FastAPI 调用 `LLMNeSy + DeepSeek + WorldEnv` 生成结构化旅行攻略，并用本地 SQLite 保存会话、消息、不可变行程版本和检索缓存。

仓库只提交前端源码和后端源码。`frontend/index.html`、`frontend/assets/`、`frontend/dist/` 都是 Vite 构建产物或旧产物，已加入 `.gitignore`，不要再提交。

## 当前功能

- 首屏是用户与 AI 的旅行意图对话，不会一上来直接生成完整行程。
- 信息足够且目的地明确时，后端会用 DeepSeek 判断是否展示“规划清单确认”；用户确认后才生成第 1 版行程。
- 生成完成后展示完成卡片，引导用户进入工作区查看和编辑。
- 工作区支持历史规划、推荐行程、只读查看、回到聊天继续修改、版本回退、归档/恢复。
- 已有行程后继续用自然语言聊天会生成新的 `ai_edit` 版本。
- 表单化编辑支持修改基础信息、每日行程、活动类型/地点/时间/费用/备注，并提供交通、住宿、餐饮、景点的类型化字段。
- 手动编辑和 AI 编辑不会覆盖旧版本；带 `base_version_id` 做冲突检测，前端可刷新到最新版本或强制另存新版本，校验失败可二次确认保存为风险版本。
- `POST /api/plan` 保持兼容，可继续用于一次性生成行程。
- 可选 Tavily 实时攻略证据、高德 Web Service demo、本地旅行记忆和推荐召回。

## 技术栈

- 后端：FastAPI、Pydantic、Uvicorn、SQLite。
- 前端：Vite、Vue 3、TypeScript、Element Plus、lucide-vue-next。
- LLM：DeepSeek OpenAI-compatible API。
- 规划链路：`chinatravel/agent/` 中的 LLMNeSy + WorldEnv。
- 数据环境：`chinatravel/environment/database/` 下的本地 CSV/JSON/SQLite 旅行数据库。
- 测试：pytest、FastAPI TestClient、前端 contract 测试，可选 Playwright 烟测脚本。

## 目录结构

```text
app/             FastAPI API、planner 服务层、实时搜索、运行状态检查
chinatravel/     原始旅行环境、agent、符号约束和数据构建脚本
frontend/src/    Vue 前端源码
tests/           后端、数据、文档和前端 contract 测试
docs/            任务拆分、设计文档和视觉参考
index.html       Vite 源码入口
vite.config.ts   Vite 开发代理和构建配置
```

构建产物说明：

```text
frontend/dist/     npm run build 输出目录，FastAPI 只在该目录存在时托管页面
frontend/assets/   旧版构建输出目录，已废弃并忽略
frontend/index.html 旧版构建输出文件，已废弃并忽略
```

## 环境准备

推荐使用 conda：

```bash
conda env create -f environment.yml
conda activate chinatravel-product
```

或者在已有 Python 3.12 环境中安装：

```bash
pip install -r requirements.txt
pip install pytest==8.4.2
```

安装前端依赖：

```bash
npm install
```

复制配置：

```bash
cp .env.example .env
```

Windows PowerShell 可用：

```powershell
Copy-Item .env.example .env
```

## 必填配置

`.env.example` 是完整配置清单，不要只复制 README 里的片段。最小真实运行至少需要：

```env
DEEPSEEK_API_KEY=你的 DeepSeek Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
CHINATRAVEL_MEMORY_DB_PATH=travel_memory.sqlite
CHINATRAVEL_TRIP_MEMORY_DB=travel_memory.sqlite
```

可选但常用：

```env
VITE_API_TARGET=http://127.0.0.1:8000
VITE_AMAP_API_KEY=你的高德 JSAPI Key
VITE_AMAP_SECURITY_CODE=你的高德安全密钥
AMAP_WEB_SERVICE_KEY=你的高德 Web Service Key
TAVILY_API_KEY=你的 Tavily Key
TAVILY_REAL_TIME_ENABLED=false
```

注意：

- `DEEPSEEK_API_KEY` 是真实规划和聊天能力的核心配置；兼容旧变量 `OPENAI_API_KEY`。
- `AMAP_WEB_SERVICE_KEY` 必须是高德 Web 服务 Key，不能用只开通 JSAPI 的前端 key 代替。
- `VITE_AMAP_API_KEY` 和 `VITE_AMAP_SECURITY_CODE` 只用于浏览器地图面板。
- `TAVILY_REAL_TIME_ENABLED=false` 时不会默认调用 Tavily，适合本地复现和测试。
- `.env` 已忽略，不要提交真实 key。

## 旅行数据库

项目依赖 ChinaTravel 本地数据库。请从上游 ChinaTravel 的 README 下载环境数据，并解压到：

```text
chinatravel/environment/database/
```

运行状态检查会验证这些目录是否存在：

```text
chinatravel/environment/database/attractions
chinatravel/environment/database/restaurants
chinatravel/environment/database/accommodations
chinatravel/environment/database/intercity_transport
chinatravel/environment/database/transportation
chinatravel/environment/database/poi
```

可选：从源数据构建轻量 SQLite：

```bash
python -m chinatravel.data.build_sqlite
```

默认 SQLite 路径：

```text
chinatravel/environment/database/chinatravel.sqlite
```

## 运行项目

启动后端：

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动前端开发服务器：

```bash
npm run dev
```

打开：

```text
http://127.0.0.1:5173/
```

Vite 会把 `/api` 代理到 `.env` 中的 `VITE_API_TARGET`，默认是 `http://127.0.0.1:8000`。

## FastAPI 托管前端

生产或演示时先构建前端：

```bash
npm run build
```

构建输出到：

```text
frontend/dist/
```

然后启动 FastAPI：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000/
```

FastAPI 只会在 `frontend/dist/` 存在时挂载静态前端。源码目录 `frontend/src/` 不会被当作静态站点托管。

## 运行状态检查

命令行：

```bash
python -c "from app.runtime_checks import check_runtime; print(check_runtime())"
```

HTTP：

```bash
curl http://127.0.0.1:8000/api/health
```

关键字段：

- `deepseek_key_configured`：是否配置 DeepSeek 或兼容 OpenAI key。
- `database_ready`：旅行数据库是否可用；`chinatravel.sqlite` 存在或旧版 CSV 数据目录齐全时为 true。
- `sqlite_database_ready`：`chinatravel.sqlite` 是否已构建。即使部分旧版 CSV 目录缺失，只要 SQLite 可用，LLMNeSy 仍可运行。
- `tavily_key_configured` / `tavily_real_time_enabled`：实时搜索配置状态。

## 核心 API

一次性生成：

```http
POST /api/plan
```

```json
{
  "query": "从上海出发去苏州玩两天，2个人，预算1300元，想轻松一点。",
  "start_city": "上海",
  "target_city": "苏州",
  "target_cities": ["苏州"],
  "days": 2,
  "people_number": 2,
  "budget": 1300,
  "use_realtime": false
}
```

对话和版本工作台：

```text
GET  /api/conversations
POST /api/conversations
GET  /api/conversations/{conversation_id}
POST /api/conversations/{conversation_id}/messages
POST /api/conversations/{conversation_id}/generate
POST /api/conversations/{conversation_id}/manual-edit
POST /api/conversations/{conversation_id}/versions/{version_id}/restore
POST /api/conversations/{conversation_id}/archive
POST /api/conversations/{conversation_id}/restore
```

推荐行程：

```text
GET  /api/recommended-plans
POST /api/recommended-plans/{recommendation_id}/open
```

辅助能力：

```text
POST /api/trip-intent/readiness
POST /api/extract-fields
GET  /api/images?q=关键词
GET  /api/amap-demo/pois
GET  /api/amap-demo/hotels
GET  /api/amap-demo/route
GET  /api/amap-demo/weather
```

## 数据和版本规则

- `conversations` 保存会话基本信息和当前版本指针。
- `conversation_messages` 保存用户和 assistant 消息，排序只依赖 `conversation_id + sequence`。
- `plan_versions` 保存完整不可变行程快照。
- `ai_generated` 表示 AI 首次生成。
- `ai_edit` 表示基于用户自然语言修改生成的新版本。
- `manual_edit` 表示表单手动编辑。
- `rollback` 表示回退生成的新快照。
- `recommended` 表示从推荐行程打开。
- 手动编辑提交完整 `TravelPlan` JSON，不做局部 patch。
- 回退不会删除旧版本，只创建新版本。
- 归档是软删除，可恢复。

## 日志

默认日志目录：

```text
logs/
```

每次规划请求会按 request id 记录：

- `api_request.json`：API 输入、request id、合并后的 planner query。
- `api_response.json`：返回给前端的完整 JSON。
- `llm_calls.jsonl`：DeepSeek 调用消息、原始响应、耗时、token 估算和错误。

LLMNeSy 运行日志：

```text
logs/LLMNeSy_DeepSeek-V3/<request_id>.log
logs/LLMNeSy_DeepSeek-V3/<request_id>.error
```

相关配置：

```env
CHINATRAVEL_LLM_TRACE_ENABLED=true
CHINATRAVEL_LLM_TRACE_CONSOLE=true
CHINATRAVEL_LLM_TRACE_CONSOLE_PROMPTS=false
CHINATRAVEL_LLM_TRACE_DIR=logs
CHINATRAVEL_AGENT_DEBUG_CONSOLE=false
```

## 测试和验证

后端与契约测试：

```bash
python -m pytest -q
```

前端构建：

```bash
npm run build
```

只跑前端 contract：

```bash
npm run test:frontend-contract
```

浏览器可视化烟测脚本已固化在 `tests/visual-smoke.mjs`。在后端和前端服务启动后运行：

```bash
node tests/visual-smoke.mjs
```

## 复现清单

1. `git clone` 仓库。
2. 创建 Python 3.12 环境并安装 `requirements.txt`。
3. `npm install`。
4. `cp .env.example .env`，至少填写 `DEEPSEEK_API_KEY`。
5. 下载并解压 ChinaTravel 数据库到 `chinatravel/environment/database/`。
6. 启动 `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`。
7. 开发模式运行 `npm run dev` 并访问 `http://127.0.0.1:5173/`。
8. 演示/生产模式运行 `npm run build`，再访问 `http://127.0.0.1:8000/`。
9. 提交前运行 `python -m pytest -q` 和 `npm run build`。

## 不提交的内容

这些文件或目录是本地配置、缓存、数据库、日志或构建产物：

```text
.env
node_modules/
logs/
cache/
tmp/
output/
travel_memory.sqlite
frontend/dist/
frontend/index.html
frontend/assets/
chinatravel/environment/database/
```

## 还没做的事

当前 M5/M6 比赛演示闭环已完成，下面是本轮已收口项：

- M5.1：自然语言继续修改会创建 `ai_edit` 新版本。
- M5.3：前端冲突处理支持刷新到最新版本或强制另存新版本。
- M5.4：活动编辑已补交通、住宿、餐饮、景点专用字段。
- M6：运行状态 UI、API 文档和浏览器手动验证脚本已补齐。

## 后续生产化

- PostgreSQL、Redis、pgvector、异步任务队列和数据治理。
