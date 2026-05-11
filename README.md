# ChinaTravel Planner

ChinaTravel Planner 是一个面向产品使用的中国旅行规划应用。用户在网页中输入自然语言旅行需求，也可以补充出发城市、目的城市、天数、人数和预算；后端通过 FastAPI 调用现有 `LLMNeSy + DeepSeek + WorldEnv` agent 体系，返回结构化 JSON 行程。

本仓库保留 `chinatravel/agent/` 下的 agent 代码，方便后续继续参考和升级。产品入口只暴露 `LLMNeSy + deepseek`。

## 功能

- 静态 HTML/CSS/JS 前端，访问 FastAPI 根路径即可使用。
- `POST /api/plan` 生成 JSON 行程规划。
- `GET /api/health` 检查 DeepSeek key 和本地旅行数据库状态。
- 支持自然语言输入与可选结构化字段组合。

## 环境准备

建议使用 Python 3.10+。

```bash
pip install -r requirements.txt
```

DeepSeek key 从环境变量读取，优先级如下：

```bash
export DEEPSEEK_API_KEY="你的 DeepSeek API Key"
# 或兼容旧配置：
export OPENAI_API_KEY="你的 DeepSeek API Key"
```

## 旅行数据库

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

## 启动

```bash
uvicorn app.main:app --reload
```

浏览器打开：

```text
http://127.0.0.1:8000/
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

## API

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

## 测试

```bash
pytest
```

当前测试覆盖：

- runtime 健康检查。
- `/api/plan` 请求/响应结构。
- planner 输入构造。
- 静态前端文件和 FastAPI 静态挂载。

## 目录

```text
app/          FastAPI 后端和 planner 服务层
frontend/     静态前端页面
chinatravel/  原始旅行环境、agent 和运行时约束模块
tests/        产品化测试
```

`chinatravel/symbol_verification/` 是 `LLMNeSy` 运行时依赖，不是可删除的评测壳子。
