# 前端 UI 优化计划

> 日期：2026-05-17
> 分支：codex/element-plus-ui-refresh
> 目标：在现有功能基础上，系统性提升前端视觉品质、交互体验和代码可维护性

---

## 0. 现状诊断

### 0.1 架构问题

| 问题 | 严重度 | 说明 |
|------|--------|------|
| App.vue 上帝组件 | 高 | 580 行 script setup，所有状态、逻辑、事件集中在一个文件 |
| 单文件 3500 行 CSS | 高 | `styles.css` 无 scoped，全局污染风险，维护困难 |
| 无状态管理 | 中 | 无 Pinia/Vuex，props drilling + emit 冒泡 |
| 无路由 | 低 | 单页状态机可接受，但 URL 不可分享 |

### 0.2 视觉问题

| 问题 | 严重度 | 说明 |
|------|--------|------|
| Element Plus 默认感强 | 高 | 组件样式偏"后台管理"，缺少旅行产品温度 |
| 聊天气泡粗糙 | 高 | `vue-element-plus-x` 默认样式偏简陋，缺少品牌感 |
| 空态首屏吸引力不足 | 中 | 三列布局信息密度高但视觉层次弱 |
| 移动端体验粗糙 | 中 | 折叠为 tab 后各面板高度/间距不统一 |
| 暗色模式对比度不足 | 低 | 部分次要文字在深色背景上可读性差 |
| 动效缺失 | 低 | 面板切换、消息出现、卡片展开无过渡 |

### 0.3 交互问题

| 问题 | 严重度 | 说明 |
|------|--------|------|
| 聊天发送后无即时反馈 | 高 | 用户发消息后需等 AI 回复才看到变化 |
| 规划清单卡片交互弱 | 中 | 字段编辑体验偏表单，缺少引导感 |
| 版本时间线信息密度低 | 中 | 版本间差异不可见，只有元信息 |
| 推荐卡片点击区域小 | 低 | 移动端容易误触 |

---

## 1. 优化目标

1. **视觉升级**：从"后台管理"感升级为"旅行工作台"感，保持紧凑密度但增加温度和层次
2. **交互打磨**：关键路径（聊天 → 生成 → 查看）的每一步都有即时反馈
3. **代码瘦身**：拆分 CSS、提取组合式函数，降低单文件复杂度
4. **移动端可用**：760px 以下体验从"勉强可用"提升到"舒适可用"

---

## 2. 优化阶段

### Phase 1：视觉基础刷新（优先级最高，1-2 天）

> 不改功能逻辑，只改样式和视觉层次

#### 1.1 设计令牌扩展

在 `styles.css` `:root` 中新增：

```css
/* 间距令牌 */
--space-xs: 4px;
--space-sm: 8px;
--space-md: 16px;
--space-lg: 24px;
--space-xl: 32px;

/* 字号令牌 */
--text-xs: 12px;
--text-sm: 13px;
--text-base: 14px;
--text-lg: 16px;
--text-xl: 20px;
--text-2xl: 24px;

/* 字重 */
--weight-normal: 400;
--weight-medium: 500;
--weight-semibold: 600;

/* 过渡 */
--ease-out: cubic-bezier(0.16, 1, 0.3, 1);
--duration-fast: 150ms;
--duration-normal: 250ms;

/* 圆角梯度 */
--radius-sm: 6px;
--radius-md: 8px;
--radius-lg: 12px;
--radius-xl: 16px;
```

#### 1.2 Header 视觉升级

- 品牌区：增加微妙的渐变底纹，品牌名加粗
- 服务状态条：从 `el-tag` 改为自定义 pill 指示器，更紧凑
- 主题切换：增加旋转过渡动画
- 整体高度从 ~64px 压缩到 ~56px，给内容区更多空间

#### 1.3 聊天面板视觉重做

- 气泡样式：从 `vue-element-plus-x` 默认改为自定义气泡
  - 用户气泡：右对齐，玉绿底色 `var(--jade-soft)`，深色文字
  - AI 气泡：左对齐，白底 `var(--panel)`，微妙阴影
  - 气泡圆角：左下/右下 4px，其余 16px（对话感）
- 输入区：圆角输入框 + 发送按钮一体化，类似 iMessage 风格
- 消息出现动画：`fadeSlideUp` 200ms

#### 1.4 推荐卡片视觉升级

- 卡片增加左侧色条（按目的地类型：山水=绿、城市=蓝、文化=琥珀）
- 悬停时微妙上浮 + 阴影加深
- 标题加粗，摘要用 `--muted` 色
- 移动端卡片全宽，点击区域增大

#### 1.5 版本时间线视觉升级

- 当前版本用玉绿圆点 + 加粗文字
- 历史版本用空心圆 + 细线连接
- 回退按钮改为文字链接样式，减少视觉噪音
- 版本来源标签用小号彩色 pill（AI生成=绿、手动编辑=蓝、回退=灰）

#### 1.6 暗色模式对比度修复

- `--quiet` 从 `#91a39b` 调亮到 `#9fb5ac`
- 次要文字确保 WCAG AA 对比度 ≥ 4.5:1
- 卡片边框从 `--line` 调亮到 `--line-strong`

---

### Phase 2：交互体验打磨（2-3 天）

> 在视觉基础上，优化关键交互路径

#### 2.1 聊天即时反馈

- 用户发送消息后，立即在消息列表中显示用户气泡（乐观更新）
- AI 回复前显示打字指示器（三个跳动的点）
- 生成行程时，聊天区显示进度卡片（替代当前全局进度条）

#### 2.2 规划清单卡片交互优化

- 清单字段改为 inline 编辑，点击即编辑
- 必填字段缺失时，字段旁显示红色小点提示
- 确认按钮在所有必填项满足后才高亮
- 增加"跳过，直接生成"的次要操作

#### 2.3 面板切换过渡

- `empty_chat` ↔ `plan_workspace` 切换时，内容区 fade + slide 过渡
- 移动端 tab 切换时，面板左右滑动过渡
- 过渡时长 250ms，使用 `--ease-out` 缓动

#### 2.4 生成完成卡片交互

- 卡片出现时从底部滑入
- "查看并编辑规划"按钮增加脉冲动画引导点击
- 点击后平滑过渡到 workspace 视图

#### 2.5 空态首屏优化

- 聊天区中央增加大号引导文案 + 示例问题气泡
- 示例问题可点击，点击后自动填入输入框并发送
- 历史为空时，侧边栏显示引导插画或空态文案

---

### Phase 3：CSS 架构重构（2 天）

> 拆分单文件 CSS，提升可维护性

#### 3.1 CSS 文件拆分

```
frontend/src/styles/
  tokens.css          # 设计令牌（颜色、间距、字号、圆角、阴影）
  element-overrides.css # Element Plus 主题覆盖
  base.css            # 重置、全局排版、滚动条
  header.css          # App header 样式
  chat.css            # 聊天面板、气泡、输入框
  sidebar.css         # 历史侧边栏
  recommendations.css # 推荐卡片
  workspace.css       # 行程工作区、版本时间线
  editor.css          # 每日行程编辑器
  responsive.css      # 响应式断点
  dark.css            # 暗色模式覆盖
  animations.css      # 过渡和动画关键帧
```

#### 3.2 组件 scoped 样式迁移

- 每个组件的样式从全局 CSS 迁移到 `<style scoped>`
- 只保留跨组件共享的令牌和工具类在全局 CSS
- 迁移顺序：TravelChatPanel → ConversationSidebar → RecommendedPlans → PlanVersionTimeline → PlanWorkspace → DailyItineraryEditor

#### 3.3 main.ts 样式导入顺序

```ts
import 'element-plus/dist/index.css'
import './styles/tokens.css'
import './styles/element-overrides.css'
import './styles/base.css'
import './styles/animations.css'
// 组件样式由 scoped 管理
import './styles/responsive.css'
import './styles/dark.css'
```

---

### Phase 4：App.vue 逻辑拆分（2 天）

> 提取组合式函数，降低 App.vue 复杂度

#### 4.1 提取 composables

```
frontend/src/composables/
  useTheme.ts          # 主题切换、持久化
  useRuntimeHealth.ts  # 服务状态检测
  useConversations.ts  # 会话列表、选择、归档、恢复
  useChat.ts           # 消息发送、清单推断、生成确认
  usePlanWorkspace.ts  # 行程工作区状态、版本回退、手动编辑
  useMobilePanel.ts    # 移动端面板切换
```

#### 4.2 App.vue 瘦身后目标

- script setup < 100 行
- 只负责组合 composables 和渲染模板
- 模板结构不变，只是数据来源从本地 ref 改为 composable 返回值

---

### Phase 5：移动端体验专项（1-2 天）

> 760px 以下从"可用"到"好用"

#### 5.1 移动端布局优化

- 底部固定 tab bar（替代顶部 el-segmented）
- tab bar 高度 56px，图标 + 文字
- 当前 tab 高亮用玉绿色
- 内容区占满剩余高度，各面板独立滚动

#### 5.2 移动端聊天优化

- 输入框固定在底部，键盘弹起时自动调整
- 消息气泡宽度最大 85%
- 长按消息可复制

#### 5.3 移动端行程查看优化

- 行程卡片改为手风琴式展开
- 地图默认折叠，点击展开
- 预算摘要固定在顶部

---

## 3. 执行优先级

| 优先级 | 阶段 | 预计工时 | 价值 |
|--------|------|----------|------|
| P0 | Phase 1 视觉基础刷新 | 1-2 天 | 用户第一印象，比赛演示最直观 |
| P1 | Phase 2 交互体验打磨 | 2-3 天 | 核心路径体验，评委操作感受 |
| P2 | Phase 3 CSS 架构重构 | 2 天 | 后续开发效率，降低样式冲突 |
| P3 | Phase 4 App.vue 逻辑拆分 | 2 天 | 代码可维护性，不影响用户 |
| P4 | Phase 5 移动端体验专项 | 1-2 天 | 移动端演示场景 |

**建议执行顺序**：Phase 1 → Phase 2 → Phase 5 → Phase 3 → Phase 4

理由：比赛演示优先，视觉和交互最直观；移动端是加分项；架构重构不影响用户但提升开发效率，放在功能稳定后做。

---

## 4. 不做的事

- 不引入 Tailwind CSS（现有令牌体系已够用，迁移成本高）
- 不引入 vue-router（单页状态机满足当前需求）
- 不引入 Pinia（composable 模式足够，避免过度工程）
- 不做国际化（中文产品，不需要 i18n）
- 不做骨架屏（加载状态用进度卡片和打字指示器替代）
- 不做复杂动画库（CSS transition + 少量 keyframe 足够）

---

## 5. 验收标准

### Phase 1 验收

- [ ] 聊天气泡有明确的用户/AI 视觉区分
- [ ] 推荐卡片有目的地类型色条和悬停效果
- [ ] 版本时间线有当前/历史视觉区分
- [ ] 暗色模式所有文字满足 WCAG AA 对比度
- [ ] `npm run build` 通过

### Phase 2 验收

- [ ] 发送消息后用户气泡立即出现
- [ ] AI 回复前有打字指示器
- [ ] 面板切换有过渡动画
- [ ] 空态首屏有示例问题可点击
- [ ] `npm run build` 通过

### Phase 3 验收

- [ ] styles/ 目录下有 10+ 个独立 CSS 文件
- [ ] styles.css 不再存在或仅做导入聚合
- [ ] 所有组件使用 scoped 样式
- [ ] `npm run build` 通过

### Phase 4 验收

- [ ] App.vue script setup < 100 行
- [ ] composables/ 目录下有 5+ 个组合式函数
- [ ] 所有功能行为不变
- [ ] `npm run build` 通过
- [ ] `python -m pytest tests/test_frontend_contract.py -q` 通过

### Phase 5 验收

- [ ] 移动端底部 tab bar 替代顶部 segmented
- [ ] 聊天输入框键盘弹起时正常
- [ ] 行程卡片手风琴展开
- [ ] Chrome DevTools 移动端模拟无水平溢出
- [ ] `npm run build` 通过

---

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| Element Plus 组件样式覆盖困难 | 使用 `:deep()` 和 CSS 优先级，不修改 node_modules |
| CSS 拆分后导入顺序问题 | tokens.css 最先导入，dark.css 最后导入 |
| composable 拆分后响应式丢失 | 每个函数返回 ref/computed，App.vue 只做组合 |
| 移动端键盘弹起布局错乱 | 使用 `visualViewport` API 监听调整 |
| 暗色模式对比度修复影响亮色 | 修改只在 `[data-theme="dark"]` 选择器内 |
