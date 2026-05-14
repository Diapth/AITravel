# ChinaTravel Planner

ChinaTravel Planner 是一个面向产品使用的中国旅行规划应用。用户在网页中输入自然语言旅行需求，也可以补充出发城市、目的城市、天数、人数和预算；后端通过 FastAPI 调用现有 `LLMNeSy + DeepSeek + WorldEnv` agent 体系，返回结构化 JSON 行程。

本仓库保留 `chinatravel/agent/` 下的 agent 代码，方便后续继续参考和升级。产品入口只暴露 `LLMNeSy + deepseek`。

## 当前功能

- Vite + Vue 3 + Element Plus 前端，访问 FastAPI 根路径即可使用构建后的工作台。
- `POST /api/plan` 生成 JSON 行程规划。
- `GET /api/health` 检查 DeepSeek key 和本地旅行数据库状态。
- 支持自然语言输入与可选结构化字段组合。
- 前端在等待规划结果时展示 DeepSeek/LLMNeSy 按天生成过程，已生成的天数会先显示。

## 技术栈

- 后端：FastAPI、Pydantic、Uvicorn。
- 前端：Vite、Vue 3、TypeScript、Element Plus、lucide-vue-next。
- LLM：DeepSeek API，使用 OpenAI SDK 兼容接口调用。
- Agent：保留原项目 `LLMNeSy` 规划链路，产品默认调用 `LLMNeSy + deepseek`。
- 数据环境：`WorldEnv` 读取本地 CSV/JSON 旅行数据库，覆盖景点、餐厅、住宿、城际交通、市内交通和 POI。
- 约束校验：`chinatravel/symbol_verification/`，用于 `LLMNeSy` 运行时检查行程约束。
- 测试：pytest、FastAPI TestClient。

## 环境准备

建议使用 conda 创建独立环境。推荐方式：

```bash
conda env create -f environment.yml
conda activate chinatravel-product
```

如果只想在已有 Python 环境中安装运行依赖：

```bash
pip install -r requirements.txt
```

前端依赖使用 npm 安装：

```bash
npm install
```

配置集中写在项目根目录的 `.env` 中。先复制示例文件：

```bash
cp .env.example .env
```

然后编辑 `.env`，填入你的 DeepSeek API Key：

```env
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_MAX_TOKENS=4096
DEEPSEEK_TEMPERATURE=0
DEEPSEEK_TOP_P=0.00000001
DEEPSEEK_TRUST_ENV_PROXY=false
DEEPSEEK_DISABLE_THINKING=false
```

后端启动时会自动读取项目根目录的 `.env`。如果你已经在 shell 中设置了 `DEEPSEEK_API_KEY` 或兼容旧配置的 `OPENAI_API_KEY`，shell 环境变量优先，不会被 `.env` 覆盖。真实 `.env` 已在 `.gitignore` 中，不会提交到仓库。

如果你使用支持思考模式的 DeepSeek 模型，并希望强制关闭思考输出，可以把 `DEEPSEEK_DISABLE_THINKING=true`。当前默认的 `deepseek-chat` 本身就是非思考模式兼容模型，通常保持 `false` 即可。

## 旅行数据库

  1. 打开 https://github.com/LAMDA-NeSy/ChinaTravel
  2. 在 README → Quick Start → Setup 中点击:
     • Google Drive   或   • NJU Drive
  3. 下载 environment.zip（或类似名称的压缩包）
产品运行依赖本地旅行数据库。请将数据库解压到：

```text
chinatravel/environment/database/
```

后端会检查以下路径：

```text
chinatravel/environment/database/attractions
chinatravel/environment/database/restaurants
chinatravel/environment/database/accommodations
chinatravel/environment/database/intercity_transport
chinatravel/environment/database/transportation
chinatravel/environment/database/poi
```

数据库目录在 `.gitignore` 中，不会提交到仓库。

## 运行项目

1. 确认健康检查依赖齐全：

```bash
python -c "from app.runtime_checks import check_runtime; print(check_runtime())"
```

期望看到：

```python
{'ok': True, 'deepseek_key_configured': True, 'database_ready': True, 'missing_database_paths': []}
```

2. 构建前端静态资源：

```bash
npm run build
```

构建会把产物写入 `frontend/index.html` 和 `frontend/assets/`，FastAPI 会从该目录挂载页面。

开发前端时也可以单独启动 Vite：

```bash
npm run dev
```

3. 启动 FastAPI：

```bash
uvicorn app.main:app --reload
```

4. 浏览器打开：

```text
http://127.0.0.1:8000/
```

5. 也可以直接请求健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

## API

## SQLite 与高德实时数据

本地 CSV/JSON 仍保留为源数据，运行时优先使用轻量 SQLite 文件：

```text
chinatravel/environment/database/chinatravel.sqlite
```

如需从源数据重建 SQLite：

```bash
python -m chinatravel.data.build_sqlite
```

当前数据边界：

- 长期稳定数据：景点快照、POI 坐标、地铁结构、火车和航班快照继续保存在本地 SQLite。
- 高频变化数据：餐厅、酒店、市内路线、天气优先通过高德 demo 接口验证实时查询能力。
- 火车和航班暂不接实时票务 API，仍使用本地快照。
- `POST /api/plan` 暂不直接依赖高德 demo，避免影响现有 LLMNeSy 主链路。

高德 demo 需要在 `.env` 中配置：

```env
AMAP_WEB_SERVICE_KEY=你的高德 Web 服务 Key
```

可用 demo 接口：

```text
GET /api/amap-demo/pois?city=苏州&keywords=餐厅
GET /api/amap-demo/hotels?city=苏州&keywords=酒店
GET /api/amap-demo/route?origin=120.1,31.1&destination=120.2,31.2&mode=driving
GET /api/amap-demo/weather?city=苏州
```

高德 demo 响应统一包含 `success`、`data`、`source`，失败时额外返回 `error`。参考能力来自高德 POI 搜索、路径规划和天气查询 Web 服务。

`POST /api/plan`

```json
{
  "query": "当前位置上海。我和女朋友想去苏州玩两天，预算1300元，请给我一个旅行规划。",
  "start_city": "上海",
  "target_city": "苏州",
  "days": 2,
  "people_number": 2,
  "budget": 1300
}
```

`query` 必填，其余字段可选。可选字段会合并进自然语言需求，帮助 DeepSeek 更稳定地解析约束。

成功响应：

```json
{
  "success": true,
  "plan": {
    "people_number": 2,
    "start_city": "上海",
    "target_city": "苏州",
    "itinerary": []
  },
  "meta": {
    "agent": "LLMNeSy",
    "llm": "deepseek",
    "elapsed_sec": 1.23
  }
}
```

失败响应：

```json
{
  "success": false,
  "error": {
    "code": "RUNTIME_NOT_READY",
    "message": "DeepSeek key 或旅行数据库未配置完成。"
  }
}
```

## 日志

每次 `POST /api/plan` 都会按 `request_id` 保存完整链路日志，默认目录是：

```text
logs/<request_id>/
```

其中包含：

- `api_request.json`：接口收到的完整输入、生成的 `request_id`、以及合并后的 planner query。
- `api_response.json`：接口返回给前端的完整 JSON 结果，包含成功或失败响应。
- `llm_calls.jsonl`：中间 DeepSeek 调用日志，每一行记录一次模型调用的 prompt messages、原始 response、耗时、token 估算和错误信息。

LLMNeSy agent 运行时的 stdout/stderr 日志会保存在：

```text
logs/LLMNeSy_DeepSeek-V3/<request_id>.log
logs/LLMNeSy_DeepSeek-V3/<request_id>.error
```

相关配置在 `.env` 中：

```env
CHINATRAVEL_LLM_TRACE_ENABLED=true
CHINATRAVEL_LLM_TRACE_DIR=logs
```

## 测试

使用 conda 环境时建议显式用当前环境的 Python 跑 pytest，避免系统或用户目录里的 `pytest` 抢占命令：

```bash
python -m pytest -q
```

当前测试覆盖：

- runtime 健康检查。
- `/api/plan` 请求/响应结构。
- planner 输入构造。
- Vite/Vue 前端文件、生成过程交互文案和 FastAPI 静态挂载。

前端构建校验：

```bash
npm run build
```

## 目录

```text
app/           FastAPI 后端和 planner 服务层
frontend/      Vue 源码和构建后的静态前端页面
chinatravel/   原始旅行环境、agent 和运行时约束模块
tests/         产品化测试
```

`chinatravel/symbol_verification/` 是 `LLMNeSy` 运行时依赖，不是可删除的评测壳子。

## 还没做的事

- 真实链路压测：目前已经完成依赖、数据库和 API 健康检查；还需要用多组真实旅行需求评估 DeepSeek 调用耗时、失败率和行程质量。
- 请求超时与取消：`/api/plan` 目前同步等待 agent 结果，后续应加入超时控制、任务队列或异步任务状态查询。
- 前端体验增强：当前页面展示 JSON 和基础 itinerary 卡片，后续可增加费用汇总、时间轴、交通段折叠、错误修复提示。
- 生产配置管理：当前本地开发使用 `.env`，后续可增加部署平台密钥管理、环境分层配置和配置校验命令。
- 日志与观测：需要结构化记录请求、耗时、token 统计、失败原因，便于后续优化 agent。
- Agent 策略扩展：当前产品入口固定 `LLMNeSy + deepseek`，保留的其他 agent 还没有暴露为可选策略。
- 部署方案：还未提供 Dockerfile、反向代理配置、生产启动脚本或 CI 流程。
