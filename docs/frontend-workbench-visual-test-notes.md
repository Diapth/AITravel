# 前端双状态工作台可视化测试问题记录

日期：2026-05-16

## 背景

本轮按 `docs/task-breakdown.md` 的 M4 前端双状态工作台推进，并使用本地 FastAPI、Vite 和 Playwright headless Chromium 做可视化 smoke test。

## 遇到的问题

### 1. Playwright 浏览器运行时缺失

现象：内置 Node runtime 中能找到 Playwright 包，但初次执行时报缺少 `chromium_headless_shell-1217`。

处理：使用 bundled Playwright CLI 执行 `playwright install chromium` 补齐本机浏览器运行时。下载完成后可正常截图。

后续建议：如果团队机器经常复现，可在开发环境初始化文档中补充一次性安装命令，或把浏览器安装纳入 CI 缓存。

### 2. 8000 端口曾运行旧后端进程

现象：`/api/health` 返回 200，但 `/api/conversations` 与 `/api/recommended-plans` 返回 404。

原因：端口上的 uvicorn 进程未加载当前分支的最新 `app/main.py`。

处理：停止旧进程并从当前工作区重新启动 `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`。

后续建议：本地联调前先打开 `/openapi.json` 搜索目标路由，确认运行进程确实对应当前代码。

### 3. 旧兼容表单隐藏但仍挂载

现象：视觉测试中出现 `el-date-picker` 未注册告警，且移动端断点把隐藏的旧兼容表单重新显示。

处理：

- 在 `frontend/src/main.ts` 注册 `ElDatePicker` 和样式。
- 将旧兼容区改为 `v-if="false"`，仅保留源码引用用于合同兼容，不参与运行时挂载。
- 修正移动端 `.workspace-grid` 样式，避免覆盖 `.legacy-plan-panel` 的隐藏策略。

后续建议：M4 后续若不再需要兼容旧合同，可删除旧 `PlannerComposer` 运行入口，只保留独立页面或测试样例。

### 4. M4.4 移动端 tab 尚未完整落地

现状：本轮完成了移动端单列堆叠与无横向滚动验证，但 `历史 / 聊天 / 行程 / 版本` 的显式 tab 切换还未实现。

可能方案：

1. 在 `App.vue` 增加 `mobilePanel` 状态，只在小屏展示分段控件。
2. 四个区域保留 DOM，但用 CSS + 状态控制当前面板，避免丢失聊天草稿。
3. 在 `tests/test_frontend_contract.py` 增加 `mobilePanel`、`mobile-workbench-tabs` 合同断言。

建议：该项作为 M4.4 的剩余收尾任务单独提交，避免与本轮 M4.1-M4.3 的服务和组件接线混在一起。

