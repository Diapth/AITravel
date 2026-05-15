# AITravel 任务拆分文档

> 依据 `docs/` 目录下现有设计、规格、实施计划和图片资产整理。本文作为团队执行视角的统一任务清单，优先采用最新文档中的确认决策；当旧方案与新方案冲突时，以 `docs/current-plan.md` 和 `docs/superpowers/plans/2026-05-15-conversational-versioned-travel-planner.md` 为准。

## 1. 文档来源

- `docs/current-plan.md`：实时搜索、旅行记忆、SSD 约束、已完成实施记录、真实 DeepSeek + Tavily 流程测试记录。
- `docs/realtime-search-and-trip-memory-design.md`：实时搜索、搜索缓存、旅行记忆、成本控制、隐私与生产化设计。
- `docs/superpowers/specs/2026-05-13-vite-vue-travel-workbench.md`：Vite + Vue 旅行规划工作台规格。
- `docs/superpowers/plans/2026-05-13-vite-vue-travel-workbench.md`：Vite + Vue 工作台实施计划。
- `docs/superpowers/plans/2026-05-15-conversational-versioned-travel-planner.md`：对话式、版本化旅行规划器实施计划。
- `docs/assets/chinatravel-architecture.png`：项目整体架构图，覆盖前端、FastAPI、chinatravel 核心包、数据与日志。
- `docs/assets/chinatravel-agent-data-flow.png`：LLMNeSy Agent 从输入 query 到搜索、约束校验、返回 plan 的运行数据流。
- `docs/assets/chinatravel-ui-prototype-reference.png` / `.svg`：对话式工作台、历史规划、推荐行程、版本记录、直接编辑器 UI 原型参考。
- `docs/assets/chinatravel-ui-prototype-reference.png`、`docs/assets/xlab-simple-test-with-provided-key.png`：视觉和图片生成验证参考资产。

## 2. 总体目标

把当前 AI 旅行规划系统推进为一个可演示、可沉淀、可迭代的本地单机产品：

1. 保留现有 `POST /api/plan` 主链路，继续由 FastAPI + LLMNeSy + DeepSeek + WorldEnv 生成结构化行程。
2. 通过 Tavily 和搜索缓存补充景区公告、预约、临时闭园、近期活动等实时信息。
3. 使用本地 SQLite 沉淀旅行请求、行程结果、反馈、相似路线统计，以及后续对话线程和版本快照。
4. 前端从单次生成页面升级为两种状态：首次聊天生成，以及已有行程工作台。
5. 支持历史规划、推荐行程、自然语言继续修改、表单直接编辑、版本回退和软删除恢复。
6. 第一版保持本地私有、单用户单机，不做账号体系、云同步、多用户公开参考。

## 3. 执行原则

所有新增任务默认遵守 SSD 工作法：

- Specification：明确输入、输出、配置、错误形态和非目标。
- Scenario：覆盖成功、缓存命中、外部服务失败、禁用开关、隐私或数据边界。
- Design：先明确模块边界、数据结构、表结构和调用链。
- Verification：实现前写测试或验收命令，实现后跑可重复验证。
- Degradation：Tavily、缓存、记忆库、DeepSeek 辅助编辑失败时，不阻断已有主链路。
- Security：外部搜索内容必须以 evidence 形式进入 LLM，不能覆盖系统或开发者指令。
- Data Governance：第一版用户记录本地私有，不公开、不跨用户展示。

## 4. 当前状态基线

### 4.1 已完成能力

- 前端已迁移为 Vue 3 + Vite + TypeScript + Element Plus + lucide-vue-next 工作台。
- 已保留 FastAPI 静态托管 `frontend/` 和现有 `/api/plan` 合同。
- 已完成 Tavily 最小客户端：
  - 文件：`app/realtime/tavily_client.py`
  - 密钥读取顺序：`TAVILY_API_KEY -> TAVILY_SEARCH_KEY`
  - 默认 `search_depth=basic`
  - 不默认返回 `raw_content`
  - 输出 `{success, evidence, usage, error}`
- 已完成实时搜索缓存：
  - 文件：`app/realtime/cache.py`
  - 表：`search_cache`
  - 缓存过期后不命中，但保留记录。
- 已完成 EvidenceCard 归一化与 prompt injection 风险标记：
  - 文件：`app/realtime/evidence.py`
- 已完成旅行记忆只写入模式：
  - 文件：`app/travel_memory.py`
  - 表：`trip_requests`、`trip_plans`、`trip_feedback`、`route_stats`
  - query 入库前脱敏手机号、邮箱、身份证号。
- 已完成 `/api/plan` 低风险接入：
  - `meta.realtime`
  - `meta.history_reuse`
  - `meta.memory_write`
  - `TAVILY_REAL_TIME_ENABLED=false` 时不主动调用 Tavily。
- 已完成真实 DeepSeek + Tavily 流程测试：
  - HTTP 200，`success=true`
  - Tavily 成功调用，`usage.credits=1`
  - 旅行记忆写入成功
  - 修复中文-only Tavily query 400 问题，改为“中文目的地 + 英文意图词”
  - 修复首次读取 `search_cache` 时表未初始化问题。

### 4.2 已知待处理问题

- 目标城市字段存在兼容问题：`target_city` 与 `target_cities` 需要统一解析，避免多城市输入被当成单个城市。
- Tavily 有时调用成功但 `evidence_count=0`，需要补充原因归因和 UI 降级提示。
- 当前 `travel_memory.sqlite` 已有旧表，但缺少对话线程、消息序列、行程版本和回退结构。
- 当前前端工作台还不是完整的“首次聊天生成 / 已有行程工作台”双状态产品。

## 5. 里程碑拆分

## M0：基线确认与文档统一

目标：确认现有能力、最新决策和任务边界，避免重复实现已完成模块。

任务：

- [x] 汇总 `docs/` 下方案、规格、实施记录和图片参考。
- [x] 明确第一版范围：单用户、单机、本地 SQLite、私有历史。
- [x] 明确兼容策略：不破坏现有 `POST /api/plan` 合同，不删除旧 SQLite 表。
- [ ] 检查当前代码与文档状态是否完全一致，尤其是测试数量、配置变量和已完成模块。

验收：

- 团队使用本文即可知道哪些任务已完成、哪些任务待做。
- 冲突决策已收敛，例如第一版不做公开参考。

## M1：阻塞问题与记忆路径收敛

目标：先解决会影响后续 conversation/version 工作台的数据一致性问题，只做后续任务的硬前置。

任务：

- [x] 统一目的地解析：
  - 新增或完善 `resolve_target_cities(request)`。
  - 统一 `target_city`、`target_cities`、自然语言拆分结果。
  - 覆盖 `build_query()`、AMap fallback、`_realtime_search_query()`、前端 payload。
- [x] 收敛旅行记忆数据库配置：
  - `CHINATRAVEL_MEMORY_DB_PATH` 作为新推荐变量。
  - `CHINATRAVEL_TRIP_MEMORY_DB` 作为旧变量兼容。
  - 读取优先级：`CHINATRAVEL_MEMORY_DB_PATH -> CHINATRAVEL_TRIP_MEMORY_DB -> travel_memory.sqlite`。
  - 测试环境优先使用临时 SQLite 文件，避免污染本地库。
- [x] 补强 Tavily 空 evidence 归因：
  - 区分 `called=true/evidence_count=0`、缓存命中、key 缺失、HTTP 失败、query 被拒绝。
  - 在 `meta.realtime` 中返回明确原因。
- [x] 补充回归测试：
  - 多目标城市解析。
  - Tavily 成功但 evidence 为空。
  - cache 表自动初始化。
  - memory DB 不可写时主链路仍成功。
  - 两个 memory DB 环境变量的优先级。

涉及文件：

- `app/planner.py`
- `app/schemas.py`
- `app/realtime/tavily_client.py`
- `app/realtime/cache.py`
- `app/realtime/evidence.py`
- `app/travel_memory.py`
- `frontend/src/services/planner.ts`
- `frontend/src/components/PlannerResults.vue`
- `tests/test_planner_api.py`
- `tests/test_tavily_client.py`
- `tests/test_realtime_cache.py`
- `tests/test_travel_memory.py`

验收命令：

```bash
python -m pytest tests/test_realtime_cache.py tests/test_planner_api.py tests/test_tavily_client.py tests/test_travel_memory.py -q
npm run build
```

## M1b：实时信息展示与记忆观测增强

目标：在 M1 稳定后增强用户可见性，不作为 conversation/version 的硬前置。

任务：

- [ ] 完善实时信息 UI 展示：
  - 展示实时来源、更新时间、缓存状态、失败降级原因。
  - 没有 evidence 时显示“未找到可靠实时来源”，不影响计划阅读。
- [ ] 完善旅行记忆写入观测：
  - 记录 request id、route key、fingerprint、使用 realtime/history 状态。
  - DB 写入失败只进入 `meta.memory_write.error`。
- [ ] 在运行状态中展示：
  - Tavily key 是否配置。
  - 实时搜索是否启用。
  - 本地记忆库路径是否可写。

验收：

```bash
python -m pytest tests/test_planner_api.py tests/test_frontend_contract.py -q
npm run build
```

## M2：对话与版本化后端最小闭环

目标：在同一个本地 SQLite 文件中增量新增 conversation/message/version 能力，先完成“创建会话 -> 生成第 1 版 -> 读取详情”的最小闭环。

### M2.1：SQLite conversation/version store

目标：只落数据层，不接 LLM，不改前端。

任务：

- [x] 增量扩展 `app/travel_memory.py`，保留旧表并新增：
  - `conversations`
  - `conversation_messages`
  - `plan_versions`
  - 可选 `conversation_messages_fts`
- [x] 实现 `TravelMemoryStore`：
  - `initialize()`
  - `create_conversation()`
  - `list_conversations()`
  - `get_conversation()`
  - `append_message()`
  - `create_plan_version()`
- [x] 保证版本编号按 conversation 递增：`1, 2, 3...`。
- [x] 保证消息排序只依赖 `conversation_id + sequence`，不依赖创建时间。

验收命令：

```bash
python -m pytest tests/test_travel_memory.py -q
```

### M2.2：Conversation API 第 1 版

目标：暴露最小 API，使前端能创建和读取一个有当前 plan 的会话。

任务：

- [x] 扩展 `app/schemas.py`：
  - `ConversationCreateRequest`
  - `ConversationSummary`
  - `ConversationMessage`
  - `PlanVersionSummary`
  - `ConversationDetailResponse`
  - `ConversationListResponse`
  - `ConversationMessageResponse`
- [x] 扩展 `app/main.py` API：
  - `GET /api/conversations`
  - `POST /api/conversations`
  - `GET /api/conversations/{conversation_id}`
  - `POST /api/conversations/{conversation_id}/messages`
- [x] 行为约束：
  - 新会话先保存用户消息，再调用现有 `get_planner().plan(PlanRequest(query=message))`。
  - planner 成功时创建 `source = "ai_generated"` 的第 1 个版本。
  - planner 失败时保留用户消息，但不创建坏版本。
  - assistant message 使用简短中文，例如 `已生成第 1 版行程。`。
  - 不修改现有 `POST /api/plan` 合同。

验收命令：

```bash
python -m pytest tests/test_conversation_api.py -q
```

### M2.3：归档、恢复与版本回退

目标：完成历史会话管理和只读版本回退，不做 AI 修改和手动编辑。

任务：

- [x] 扩展 `TravelMemoryStore`：
  - `archive_conversation()`
  - `restore_conversation()`
  - `restore_version()`
- [x] 扩展 API：
  - `POST /api/conversations/{conversation_id}/archive`
  - `POST /api/conversations/{conversation_id}/restore`
  - `POST /api/conversations/{conversation_id}/versions/{version_id}/restore`
- [x] 行为约束：
  - 归档只改 `conversations.status = archived`。
  - 恢复只改回 `active`。
  - 回退创建 `source = "rollback"` 的新版本，不删除旧版本。
  - 回退后追加 assistant message 说明已回退。

涉及文件：

- `app/travel_memory.py`
- `app/schemas.py`
- `app/main.py`
- `tests/conftest.py`
- `tests/test_travel_memory.py`
- `tests/test_conversation_api.py`

验收命令：

```bash
python -m pytest tests/test_travel_memory.py tests/test_conversation_api.py -q
```

## M3：推荐行程与历史召回

目标：让首次进入时有可打开的推荐行程，已有历史可作为推荐来源，并保持本地私有。

任务：

- [x] 先做静态 fallback 推荐：
  - 无历史数据时 `GET /api/recommended-plans` 返回静态样例。
  - 样例必须可直接打开为 conversation。
- [ ] 推荐来源分层：
  - 优先返回 `plan_versions` 中高质量版本。
  - 其次 fallback 到旧 `trip_plans`。
  - 最后 fallback 到静态样例，如“桂林阳朔 4 天 3 晚”。
- [x] 推荐卡片字段：
  - `id`
  - `title`
  - `summary`
  - `source`
  - `plan`
  - 可选 `conversation_id`
  - 可选 `version_id`
- [x] 点击推荐后立即创建 conversation：
  - 创建一条 assistant message：`已打开推荐行程，可继续告诉我你想怎么调整。`
  - 创建 `source = "recommended"` 的首个 plan version。
  - conversation title 来源于推荐标题。
- [ ] 复用旧旅行记忆：
  - 使用 `request_fingerprint`、`route_key`、`route_stats` 做候选召回。
  - 低质量或过期计划不进入推荐池。
- [ ] 第一版不做跨用户推荐：
  - 不暴露其他用户原文。
  - 不做公开参考入口。

涉及文件：

- `app/travel_memory.py`
- `app/main.py`
- `app/schemas.py`
- `frontend/src/services/planner.ts`
- `frontend/src/components/RecommendedPlans.vue`
- `frontend/src/App.vue`
- `tests/test_conversation_api.py`

验收：

- 无历史数据时 `GET /api/recommended-plans` 仍返回静态样例。
- 点击任一推荐后可进入可继续聊天和回退的工作台。

## M4：前端双状态工作台

目标：把前端升级为“首次进入聊天生成 / 已有行程工作台”两种状态，匹配 UI 原型。

### M4.1：服务层与应用状态机

目标：先让前端能调用新 API，并能在 `empty_chat` 和 `plan_workspace` 之间切换。

任务：

- [ ] 扩展前端服务层：
  - `requestConversations`
  - `createConversation`
  - `requestConversationDetail`
  - `sendConversationMessage`
  - `restorePlanVersion`
  - `saveManualPlanEdit`
  - `archiveConversation`
  - `restoreConversation`
  - `requestRecommendedPlans`
  - `openRecommendedPlan`
- [ ] 修改 `App.vue`：
  - 增加状态机：
    - `empty_chat`
    - `plan_workspace`
  - 首次聊天创建 conversation。
  - 选择历史打开 workspace。
  - 选择推荐打开 workspace。
  - 保存、回退、归档、恢复后刷新详情。

验收：

```bash
python -m pytest tests/test_frontend_contract.py -q
npm run build
```

### M4.2：空态三列工作台

目标：形成可演示首屏，但右侧行程详情可以暂时只读或空白。

任务：

- [ ] 新建 `ConversationSidebar.vue`：
  - 展示 `历史规划`
  - 新建规划
  - 归档 / 恢复
  - 按更新时间排序。
- [ ] 新建 `TravelChatPanel.vue`：
  - 展示对话消息。
  - 初始态用于描述旅行需求。
  - 行程态用于 `继续修改`。
- [ ] 新建 `RecommendedPlans.vue`：
  - 展示 `推荐行程`。
  - 支持点击打开行程。

### M4.3：只读行程工作区与版本线

目标：打开历史或推荐后，能查看当前行程和版本记录。

任务：

- [ ] 新建 `PlanVersionTimeline.vue`：
  - 展示 `版本记录`。
  - 当前版本高亮。
  - 非当前版本可 `回退到此版本`。
- [ ] 新建 `PlanWorkspace.vue`：
  - 模式切换：`只读` / `编辑`。
  - 只读态复用 `PlannerResults`。
  - 编辑态第一版只保留“继续用自然语言修改”入口，直接编辑器后置到 M5。
- [ ] 修改 `PlannerResults.vue`：
  - 支持外部传入已有 `PlanResponse` 或 `TravelPlan`。
  - 降低对“生成中模拟进度”的耦合。

### M4.4：响应式样式收尾

目标：在桌面和移动端保持可用，不在首版追求复杂动效。

任务：

- [ ] 修改 `frontend/src/styles.css`：
  - 延续温润纸色、瓷白面板、玉绿色主按钮、朱砂/琥珀风险提示、紧凑工作台风格。
  - 桌面空态三列：历史 / 聊天 / 推荐。
  - 桌面行程态两列：对话版本栏 / 行程工作区。
  - 移动端折叠为历史、聊天、行程、版本 tab。

涉及文件：

- `frontend/src/services/planner.ts`
- `frontend/src/App.vue`
- `frontend/src/components/ConversationSidebar.vue`
- `frontend/src/components/TravelChatPanel.vue`
- `frontend/src/components/RecommendedPlans.vue`
- `frontend/src/components/PlanVersionTimeline.vue`
- `frontend/src/components/PlanWorkspace.vue`
- `frontend/src/components/PlannerResults.vue`
- `frontend/src/styles.css`
- `tests/test_frontend_contract.py`

验收命令：

```bash
python -m pytest tests/test_frontend_contract.py -q
npm run build
```

## M5：AI 修改、手动编辑与版本冲突

目标：在最小工作台稳定后，再加入可变更当前行程的能力。先做 AI 修改，再做直接编辑器。

### M5.1：自然语言继续修改

目标：用户在已有行程上继续聊天，系统创建新的 `ai_edit` 版本。

任务：

- [ ] 新增 DeepSeek 行程修改助手：
  - 文件：`app/assistants.py`
  - 函数：`revise_plan_with_chat(current_plan, recent_messages, user_message)`
  - 要求返回完整 plan JSON，而不是局部 patch。
- [ ] 扩展 `POST /api/conversations/{conversation_id}/messages`：
  - 有 current plan 时调用 `revise_plan_with_chat()`。
  - 创建 `source = "ai_edit"` 的新版本。
  - assistant message 简短说明新版本号。
- [ ] 加入基础冲突检测：
  - 请求带 `base_version_id`。
  - 服务端当前版本已变化且未 override 时返回 `VERSION_CONFLICT`。

### M5.2：直接编辑器最小版

目标：先支持完整 plan JSON 的表单化编辑保存，不追求所有活动类型字段一次到位。

任务：

- [ ] 设计手动编辑数据契约：
  - 前端提交完整 `TravelPlan` JSON。
  - 后端保存完整不可变快照。
- [ ] 新建 `DailyItineraryEditor.vue`：
  - 支持行程摘要字段编辑。
  - 支持每日行程和活动的增删改。
  - 第一版可使用通用字段：标题、类型、地点、时间、费用、备注。
  - 交通、住宿、餐饮、景点专用字段后置到 M5.4。
- [ ] 基础校验：
  - 顶层字段必须是对象。
  - `itinerary` 必须是数组。
  - 每天至少包含可识别 day 信息。
  - activity 必须有类型和必要字段。
- [ ] 校验失败流程：
  - 前端展示 inline warning。
  - 弹窗提供 `返回修改` 和 `仍然保存`。
  - 后端 `validation_override=true` 时仍创建版本。
  - 带 warning 的版本在时间线显示风险标记。

### M5.3：冲突与风险标记补齐

任务：

- [ ] 版本冲突流程：
  - 前端提交当前 `base_version_id`。
  - 后端发现当前版本变化时返回冲突。
  - 前端提供 `刷新到最新版本` 和 `仍另存新版本`。
  - 用户强制保存时使用 `conflict_override=true`。
- [ ] 版本时间线展示：
  - `AI生成`
  - `AI修改`
  - `手动编辑`
  - `回退`
  - `推荐`
  - 校验风险标记。

### M5.4：类型化活动编辑增强

任务：

- [ ] 交通字段：start、end、TrainID/transportation、start time、end time、duration、seat label、ticket count、cost。
- [ ] 住宿字段：hotel/place、city、check-in time、check-out time、rooms、price、cost、notes。
- [ ] 餐饮字段：restaurant/place、city、time range、recommended food、per-person price、cost、notes。
- [ ] 景点/活动字段：title/place、city、time range、transport、ticket price/count、cost、notes。

涉及文件：

- `app/main.py`
- `app/travel_memory.py`
- `app/schemas.py`
- `frontend/src/components/DailyItineraryEditor.vue`
- `frontend/src/components/PlanVersionTimeline.vue`
- `frontend/src/components/PlanWorkspace.vue`
- `tests/test_conversation_api.py`
- `tests/test_frontend_contract.py`

验收：

- 手动编辑不会覆盖旧版本。
- 回退不会删除旧版本。
- 冲突和校验风险都能被用户看见。

## M6：运行状态、文档与配置

目标：让开发、演示和评审能清楚理解配置、API、存储模型和风险边界。

任务：

- [ ] 更新 `.env.example`：
  - `TAVILY_API_KEY`
  - `TAVILY_SEARCH_KEY`
  - `TAVILY_REAL_TIME_ENABLED=false`
  - `CHINATRAVEL_TAVILY_SEARCH_DEPTH=basic`
  - `CHINATRAVEL_TAVILY_MAX_RESULTS=5`
  - `CHINATRAVEL_TAVILY_DAILY_CREDIT_LIMIT=500`
  - `CHINATRAVEL_HISTORY_REUSE_ENABLED=false`
  - `CHINATRAVEL_MEMORY_DB_PATH=travel_memory.sqlite`
  - `CHINATRAVEL_TRIP_MEMORY_DB=travel_memory.sqlite`（旧变量兼容）
  - `CHINATRAVEL_RAW_QUERY_RETENTION_DAYS=30`
- [ ] 更新 README：
  - 新增 conversation API 文档。
  - 新增推荐行程 API 文档。
  - 说明 `conversation_messages` 使用 `conversation_id + sequence` 排序。
  - 说明 `plan_versions` 是完整不可变快照。
  - 说明 rollback 创建新版本。
  - 说明 archive 是软删除。
  - 说明本阶段是本地单机历史，不做云同步和多用户共享。
- [ ] 更新运行状态 UI：
  - FastAPI 运行中。
  - DeepSeek 运行中。
  - 本地记忆库状态。
  - Tavily 实时搜索是否启用。
- [ ] 补充手动验证脚本或步骤：
  - 首次聊天生成。
  - 点击推荐打开。
  - 继续修改。
  - 直接编辑保存。
  - 回退版本。
  - 归档和恢复。

涉及文件：

- `.env.example`
- `README.md`
- `frontend/src/App.vue`
- `frontend/src/components/*`
- `app/runtime_checks.py`

验收：

```bash
python -m pytest -q
npm run build
```

## M7：生产化后续增强

目标：在比赛演示版稳定后，为更高访问量、更强检索和更完整数据治理做准备。

任务：

- [ ] SQLite 迁移到 PostgreSQL。
- [ ] Redis 热缓存：
  - Tavily 搜索结果。
  - 推荐行程。
  - 热门城市统计。
- [ ] 引入 `pgvector`：
  - 相似请求召回。
  - 相似行程召回。
  - POI 和偏好召回。
- [ ] 异步任务队列：
  - 热门目的地实时信息定时刷新。
  - 过期缓存清理。
  - 原始 query 保留 30 天后的脱敏/删除。
- [ ] 数据治理：
  - 导出用户数据。
  - 删除用户数据。
  - 数据保留任务审计。
- [ ] 质量推荐：
  - `poi_stats`
  - `cost_events`
  - `data_retention_jobs`
  - 低评分计划自动降权。

验收：

- 生产化任务不阻塞 M1-M6 的比赛演示闭环。
- 每项增强都有独立迁移和回滚方案。

## 6. 推荐执行顺序

1. M1：先修目的地解析、Tavily 空 evidence meta、memory DB 路径兼容。
2. M2.1：实现 conversation/version SQLite store。
3. M2.2：实现创建会话、发消息生成第 1 版、读取详情。
4. M3：先接静态推荐打开，再做历史推荐分层。
5. M4.1-M4.3：完成前端最小双状态和只读行程工作台。
6. M2.3：补归档、恢复、版本回退。
7. M5.1：自然语言继续修改生成 `ai_edit` 版本。
8. M5.2-M5.4：直接编辑器、冲突和类型化字段增强。
9. M1b/M6：补实时展示、运行状态、README 和手动验证。
10. M7：视比赛后需求进入生产化增强。

## 7. 验收总清单

- [ ] `POST /api/plan` 合同保持兼容。
- [ ] Tavily 默认关闭，开启后使用 basic 搜索深度。
- [ ] 自动化测试不真实调用 Tavily。
- [ ] Tavily、缓存、memory 任一失败不阻断主规划。
- [ ] 外部搜索内容以 EvidenceCard 进入 LLM。
- [ ] 本地 SQLite 保留旧表，新增表增量创建。
- [ ] 对话消息按 `conversation_id + sequence` 稳定排序。
- [ ] 行程版本不可变，所有修改创建新版本。
- [ ] 回退创建 `rollback` 新版本，不删除旧版本。
- [ ] 直接编辑提交完整 `TravelPlan` JSON。
- [ ] 校验失败可二次确认保存，并显示风险标记。
- [ ] 版本冲突可刷新或另存新版本。
- [ ] 归档是软删除，可恢复。
- [ ] 推荐行程无历史时有静态 fallback。
- [ ] 第一版不做公开参考、不做云同步、不做多用户权限。
- [ ] README 和 `.env.example` 覆盖新增配置与 API。
- [ ] 前端 contract 测试通过。
- [ ] `npm run build` 通过。
- [ ] `python -m pytest -q` 通过。

## 8. 风险与处理策略

| 风险 | 影响 | 处理策略 |
| --- | --- | --- |
| Tavily 返回空 evidence | 用户看不到实时来源 | 在 `meta.realtime` 和 UI 中明确原因，不阻断行程 |
| DeepSeek 修改行程返回非法 JSON | AI 编辑失败 | 返回业务错误，保留用户消息，不创建坏版本 |
| SQLite 写入锁冲突 | 历史或版本保存失败 | 写操作短事务，失败进入业务错误或 meta，不阻断读/主链路 |
| 手动编辑结构不完整 | 行程展示异常 | 前后端基础校验，允许风险保存但显式标记 |
| 多标签页基于旧版本编辑 | 覆盖用户新版本 | 使用 `base_version_id` 冲突检测 |
| 旧表与新表职责混淆 | 迁移风险 | 旧表保留用于搜索缓存、统计和 fallback，新表专注 conversation/version |
| 隐私边界被误扩展 | 数据治理风险 | 第一版只做本地私有，不增加公开分享字段或跨用户展示 |

## 9. 本轮建议优先落地任务

为了最快形成可演示闭环，建议下一轮从以下任务开始：

1. 统一 `target_city` / `target_cities` 解析，修复多城市输入链路。
2. 统一 memory DB 环境变量优先级，补临时库测试。
3. 实现 `conversations`、`conversation_messages`、`plan_versions` 增量表和 store 测试。
4. 注册最小 conversation API：list、create、detail、send message。
5. 接静态推荐打开，保证首屏有内容。
6. 前端接 `empty_chat` 三列和只读 `plan_workspace`。
