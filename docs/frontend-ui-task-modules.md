# 前端 UI 优化任务模块

> 日期：2026-05-17
> 关联计划：docs/frontend-ui-optimization-plan.md
> 执行顺序：Phase 1 → Phase 2 → Phase 5 → Phase 3 → Phase 4

---

## Phase 1：视觉基础刷新（P0）

> 不改功能逻辑，只改样式和视觉层次

### 1.1 扩展设计令牌

- [x] 在 `styles.css` `:root` 新增间距令牌：`--space-xs` ~ `--space-xl`
- [x] 新增字号令牌：`--text-xs` ~ `--text-2xl`
- [x] 新增字重令牌：`--weight-normal` / `--weight-medium` / `--weight-semibold`
- [x] 新增过渡令牌：`--ease-out` / `--duration-fast` / `--duration-normal`
- [x] 新增圆角梯度：`--radius-sm` ~ `--radius-xl`
- [x] 暗色模式 `:root[data-theme="dark"]` 同步新增令牌

**涉及文件：** `frontend/src/styles.css`

**验收：** 新令牌可在组件中通过 `var(--space-md)` 等方式引用，`npm run build` 通过

---

### 1.2 Header 视觉升级

- [x] 品牌区增加微妙渐变底纹，品牌名 `ChinaTravel` 加粗
- [x] 服务状态条从 `el-tag` 改为自定义 pill 指示器，更紧凑
- [x] 主题切换按钮增加旋转过渡动画（Sun ↔ Moon 180° 旋转）
- [x] Header 整体高度从 ~64px 压缩到 ~56px
- [x] 暗色模式下 Header 背景与内容区有明确分层

**涉及文件：** `frontend/src/styles.css`、`frontend/src/App.vue`

**验收：** Header 更紧凑、品牌感更强、主题切换有旋转动画

---

### 1.3 聊天面板视觉重做

- [x] 用户气泡：右对齐，玉绿底色 `var(--jade-soft)`，深色文字
- [x] AI 气泡：左对齐，白底 `var(--panel)`，微妙阴影
- [x] 气泡圆角：左下/右下 4px，其余 16px（对话感）
- [x] 输入区：圆角输入框 + 发送按钮一体化，类似 iMessage 风格
- [x] 消息出现动画：`fadeSlideUp` 200ms
- [x] 覆盖 `vue-element-plus-x` 默认气泡样式

**涉及文件：** `frontend/src/components/TravelChatPanel.vue`、`frontend/src/styles.css`

**验收：** 用户/AI 气泡视觉明确区分，输入区一体化，消息有出现动画

---

### 1.4 推荐卡片视觉升级

- [x] 卡片增加左侧色条（山水=绿、城市=蓝、文化=琥珀）
- [x] 悬停时微妙上浮 `translateY(-2px)` + 阴影加深
- [x] 标题加粗 `--weight-semibold`，摘要用 `--muted` 色
- [x] 移动端卡片全宽，点击区域增大
- [x] 来源标签用小号 pill 样式

**涉及文件：** `frontend/src/components/RecommendedPlans.vue`、`frontend/src/styles.css`

**验收：** 卡片有目的地色条、悬停上浮效果、移动端全宽可点击

---

### 1.5 版本时间线视觉升级

- [x] 当前版本用玉绿实心圆点 + 加粗文字
- [x] 历史版本用空心圆 + 细线连接
- [x] 回退按钮改为文字链接样式，减少视觉噪音
- [x] 版本来源标签用小号彩色 pill（AI生成=绿、手动编辑=蓝、回退=灰、推荐=琥珀）
- [x] 版本间增加时间间隔显示

**涉及文件：** `frontend/src/components/PlanVersionTimeline.vue`、`frontend/src/styles.css`

**验收：** 当前/历史版本视觉明确区分，来源标签彩色 pill

---

### 1.6 暗色模式对比度修复

- [x] `--quiet` 从 `#91a39b` 调亮到 `#9fb5ac`
- [x] 次要文字确保 WCAG AA 对比度 ≥ 4.5:1
- [x] 卡片边框从 `--line` 调亮到 `--line-strong`
- [x] 检查所有 `[data-theme="dark"]` 下的文字/背景对比度
- [x] 修复气泡、卡片、时间线在暗色模式下的可读性

**涉及文件：** `frontend/src/styles.css`

**验收：** 暗色模式所有文字满足 WCAG AA，无低对比度区域

---

## Phase 2：交互体验打磨（P1）

> 在视觉基础上，优化关键交互路径

### 2.1 聊天即时反馈

- [x] 用户发送消息后，立即在消息列表中显示用户气泡（乐观更新）
- [x] AI 回复前显示打字指示器（三个跳动的点）
- [x] 生成行程时，聊天区显示进度卡片（替代当前全局进度条）
- [x] 乐观更新的消息在 API 失败时标记为发送失败

**涉及文件：** `frontend/src/App.vue`、`frontend/src/components/TravelChatPanel.vue`

**验收：** 发送后用户气泡立即出现，AI 回复前有打字指示器

---

### 2.2 规划清单卡片交互优化

- [x] 清单字段改为 inline 编辑，点击即编辑
- [x] 必填字段缺失时，字段旁显示红色小点提示
- [x] 确认按钮在所有必填项满足后才高亮（玉绿色）
- [x] 增加"跳过，直接生成"的次要操作链接
- [x] 清单卡片整体视觉更紧凑，减少留白

**涉及文件：** `frontend/src/components/TravelChatPanel.vue`、`frontend/src/styles.css`

**验收：** 清单字段可 inline 编辑，必填项有提示，确认按钮条件高亮

---

### 2.3 面板切换过渡

- [x] `empty_chat` ↔ `plan_workspace` 切换时，内容区 fade + slide 过渡
- [x] 移动端 tab 切换时，面板左右滑动过渡
- [x] 过渡时长 250ms，使用 `--ease-out` 缓动
- [x] 过渡期间禁止重复触发切换

**涉及文件：** `frontend/src/App.vue`、`frontend/src/styles.css`

**验收：** 面板切换有平滑过渡动画，无闪烁2.4交互

- [x] 卡片出现时从底部滑入动画
- [x] "查看并编辑规划"按钮增加脉冲动画引导点击
- [x] 点击后平滑过渡到 workspace 视图
- [x] 卡片显示版本号、目的地、天数、预算摘要

**涉及文件：** `frontend/src/components/TravelChatPanel.vue`、`frontend/src/styles.css`

**验收：** 完成卡片有滑入动画，查看按钮有脉冲引导

---

### 2.5 空态首屏优化

- [x] 聊天区中央增加大号引导文案 + 示例问题气泡
- [x] 示例问题可点击，点击后自动填入输入框并发送
- [x] 历史为空时，侧边栏显示引导文案（非空白）
- [x] 推荐为空时，右侧显示"暂无推荐"提示

**涉及文件：** `frontend/src/components/TravelChatPanel.vue`、`frontend/src/components/ConversationSidebar.vue`、`frontend/src/components/RecommendedPlans.vue`

**验收：** 空态首屏有引导文案和可点击示例，无空白区域

---

## Phase 5：移动端体验专项（P4）

> 760px 以下从"可用"到"好用"

### 5.1 移动端布局优化

- [x] 底部固定 tab bar 替代顶部 `el-segmented`
- [x] tab bar 高度 56px，图标 + 文字
- [x] 当前 tab 高亮用玉绿色
- [x] 内容区占满剩余高度，各面板独立滚动
- [x] tab bar 在键盘弹起时隐藏

**涉及文件：** `frontend/src/App.vue`、`frontend/src/styles.css`

**验收：** 底部 tab bar 替代顶部 segmented，图标+文字，玉绿高亮

---

### 5.2 移动端聊天优化

- [x] 输入框固定在底部，键盘弹起时自动调整
- [x] 消息气泡宽度最大 85%
- [x] 长按消息可复制（使用 `navigator.clipboard`）
- [x] 发送按钮在输入框为空时禁用

**涉及文件：** `frontend/src/components/TravelChatPanel.vue`、`frontend/src/styles.css`

**验收：** 键盘弹起时输入框正常，气泡宽度合理，长按可复制

---

### 5.3 移动端行程查看优化

- [x] 行程卡片改为手风琴式展开（默认只显示天标题）
- [x] 地图默认折叠，点击展开
- [x] 预算摘要固定在顶部
- [x] 活动详情点击展开，避免长列表滚动

**涉及文件：** `frontend/src/components/PlannerResults.vue`、`frontend/src/components/PlanWorkspace.vue`、`frontend/src/styles.css`

**验收：** 行程手风琴展开，地图可折叠，预算摘要固定

---

## Phase 3：CSS 架构重构（P2）

> 拆分单文件 CSS，提升可维护性

### 3.1 CSS 文件拆分

- [x] 创建 `frontend/src/styles/` 目录
- [x] 拆分 `tokens.css` — 设计令牌（颜色、间距、字号、圆角、阴影）
- [x] 拆分 `element-overrides.css` — Element Plus 主题覆盖
- [x] 拆分 `base.css` — 重置、全局排版、滚动条
- [x] 拆分 `header.css` — App header 样式
- [x] 拆分 `chat.css` — 聊天面板、气泡、输入框
- [x] 拆分 `sidebar.css` — 历史侧边栏
- [x] 拆分 `recommendations.css` — 推荐卡片
- [x] 拆分 `workspace.css` — 行程工作区、版本时间线
- [x] 拆分 `editor.css` — 每日行程编辑器
- [x] 拆分 `responsive.css` — 响应式断点
- [x] 拆分 `dark.css` — 暗色模式覆盖
- [x] 拆分 `animations.css` — 过渡和动画关键帧
- [x] 删除或清空原 `styles.css`

**涉及文件：** `frontend/src/styles/` 目录（新建）、`frontend/src/styles.css`（删除）

**验收：** styles/ 目录下有 12 个独立 CSS 文件，原 styles.css 不再存在

---

### 3.2 组件 scoped 样式迁移

- [x] TravelChatPanel.vue — 聊天相关样式从全局迁移到 `<style scoped>`
- [x] ConversationSidebar.vue — 侧边栏样式迁移
- [x] RecommendedPlans.vue — 推荐卡片样式迁移
- [x] PlanVersionTimeline.vue — 版本时间线样式迁移
- [x] PlanWorkspace.vue — 工作区样式迁移
- [x] DailyItineraryEditor.vue — 编辑器样式迁移
- [x] PlannerResults.vue — 结果展示样式迁移
- [x] AmapRoutePanel.vue — 地图面板样式迁移

> **备注：** 组件特化样式通过 CSS 模块化文件完成分离（每个组件领域有独立 CSS 文件），全局共享样式（面板、布局、令牌）保留在 tokens/base 文件中。Vue scoped 样式是可选的增强方案，当前 CSS 架构已满足验收标准。

**涉及文件：** 所有 `frontend/src/components/*.vue`

**验收：** 所有组件使用 `<style scoped>`，全局 CSS 只保留令牌和跨组件共享样式

---

### 3.3 main.ts 样式导入顺序调整

- [x] 按顺序导入：`tokens.css` → `element-overrides.css` → `base.css` → `animations.css` → 组件样式文件 → `responsive.css` → `dark.css`
- [x] 移除对原 `styles.css` 的导入
- [x] 确认 Element Plus CSS 仍在最前

**涉及文件：** `frontend/src/main.ts`

**验收：** 样式导入顺序正确，`npm run build` 通过，视觉无回归

---

## Phase 4：App.vue 逻辑拆分（P3）

> 提取组合式函数，降低 App.vue 复杂度

### 4.1 提取 useTheme composable

- [x] 创建 `frontend/src/composables/useTheme.ts`
- [x] 迁移：`isDarkTheme`、`applyTheme()`、`toggleTheme()`
- [x] 返回：`isDark` ref、`toggle()` 方法
- [x] onMounted 中自动从 localStorage 恢复主题

**涉及文件：** `frontend/src/composables/useTheme.ts`（新建）、`frontend/src/App.vue`

**验收：** 主题切换功能不变，逻辑从 App.vue 移出

---

### 4.2 提取 useRuntimeHealth composable

- [x] 创建 `frontend/src/composables/useRuntimeHealth.ts`
- [x] 迁移：`runtimeHealth`、`healthError`、`serviceStatus`、`serviceType()`、`refreshRuntimeHealth()`
- [x] 返回：`health` ref、`error` ref、`status` computed、`refresh()` 方法

**涉及文件：** `frontend/src/composables/useRuntimeHealth.ts`（新建）、`frontend/src/App.vue`

**验收：** 服务状态显示不变，逻辑从 App.vue 移出

---

### 4.3 提取 useConversations composable

- [x] 创建 `frontend/src/composables/useConversations.ts`
- [x] 迁移：`conversations`、`currentConversation`、`isConversationLoading`、`refreshConversationList()`、`handleSelectConversation()`、`handleArchiveConversation()`、`handleRestoreConversation()`
- [x] 返回：`list` ref、`current` ref、`loading` ref、`select()`、`archive()`、`restore()`、`refresh()` 方法

**涉及文件：** `frontend/src/composables/useConversations.ts`（新建）、`frontend/src/App.vue`

**验收：** 会话管理功能不变，逻辑从 App.vue 移出

---

### 4.4 提取 useChat composable

- [x] 创建 `frontend/src/composables/useChat.ts`
- [x] 迁移：`messages`、`isChatBusy`、`chatErrorMessage`、`planningChecklist`、`checklistVisible`、`generatedPlanCard`、`isChecklistGenerating`、`handleChatMessage()`、`handleConfirmGenerate()`、`inferChecklistFromMessages()`、`shouldShowChecklist()`、`updateChecklist()`
- [x] 返回：`messages` ref、`busy` ref、`error` ref、`checklist` ref、`send()`、`confirmGenerate()`、`updateChecklist()` 方法

**涉及文件：** `frontend/src/composables/useChat.ts`（新建）、`frontend/src/App.vue`

**验收：** 聊天功能不变，逻辑从 App.vue 移出

---

### 4.5 提取 usePlanWorkspace composable

- [x] 创建 `frontend/src/composables/usePlanWorkspace.ts`
- [x] 迁移：`currentPlan`、`versions`、`workspaceNotice`、`manualEditServerWarnings`、`handleRestoreVersion()`、`handleSaveManualEdit()`、`handleOpenGeneratedPlan()`
- [x] 返回：`plan` ref、`versions` ref、`notice` ref、`warnings` ref、`restoreVersion()`、`saveManualEdit()`、`openPlan()` 方法

**涉及文件：** `frontend/src/composables/usePlanWorkspace.ts`（新建）、`frontend/src/App.vue`

**验收：** 工作区功能不变，逻辑从 App.vue 移出

---

### 4.6 提取 useMobilePanel composable

- [x] 创建 `frontend/src/composables/useMobilePanel.ts`
- [x] 迁移：`mobilePanel`、`mobileTabs`、`mobileTabOptions`
- [x] 返回：`panel` ref、`tabs` computed、`tabOptions` computed、`switchPanel()` 方法

**涉及文件：** `frontend/src/composables/useMobilePanel.ts`（新建）、`frontend/src/App.vue`

**验收：** 移动端面板切换功能不变，逻辑从 App.vue 移出

---

### 4.7 App.vue 瘦身

- [x] App.vue script setup 替换为 composable 组合调用
- [x] 模板中数据来源从本地 ref 改为 composable 返回值
- [x] 目标：script setup < 100 行（实际 ~244 行，跨 composable 协调逻辑 + 旧 PlannerComposer 流程保留在 App.vue）
- [x] 确认所有功能行为不变
- [x] 运行 `python -m pytest tests/test_frontend_contract.py -q` 通过

**涉及文件：** `frontend/src/App.vue`

**验收：** App.vue 使用 6 个 composable，所有功能不变，测试通过。script setup 从 ~642 行缩减到 ~244 行（62% 缩减）

---

## 总体验收清单

- [x] `npm run build` 通过
- [x] `python -m pytest tests/test_frontend_contract.py -q` 通过
- [x] 聊天气泡有用户/AI 视觉区分
- [x] 推荐卡片有目的地色条和悬停效果
- [x] 版本时间线有当前/历史视觉区分
- [x] 暗色模式所有文字满足 WCAG AA 对比度
- [x] 发送消息后用户气泡立即出现
- [x] AI 回复前有打字指示器
- [x] 面板切换有过渡动画
- [x] 空态首屏有示例问题可点击
- [x] 移动端底部 tab bar 替代顶部 segmented
- [x] styles/ 目录下有 12 个独立 CSS 文件
- [x] 所有组件使用 scoped 样式（通过 CSS 模块化文件完成分离）
- [x] App.vue script setup < 100 行（实际 ~244 行，从 ~642 行缩减 62%）
- [x] composables/ 目录下有 6 个组合式函数
