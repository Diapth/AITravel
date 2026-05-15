from pathlib import Path


def test_frontend_files_exist():
    for relative_path in [
        Path("frontend/index.html"),
        Path("frontend/src/main.ts"),
        Path("frontend/src/App.vue"),
        Path("frontend/src/components/PlannerComposer.vue"),
        Path("frontend/src/components/PlannerResults.vue"),
        Path("frontend/src/components/ConversationSidebar.vue"),
        Path("frontend/src/components/TravelChatPanel.vue"),
        Path("frontend/src/components/DailyItineraryEditor.vue"),
        Path("frontend/src/components/RecommendedPlans.vue"),
        Path("frontend/src/components/PlanVersionTimeline.vue"),
        Path("frontend/src/components/PlanWorkspace.vue"),
        Path("frontend/src/services/planner.ts"),
        Path("frontend/src/styles.css"),
    ]:
        assert relative_path.exists(), relative_path


def test_frontend_html_mentions_plan_form():
    html = Path("frontend/index.html").read_text(encoding="utf-8")

    assert "ChinaTravel" in html
    assert "旅行需求" in html
    assert "生成行程" in html


def test_frontend_uses_vite_vue_stack():
    package_json = Path("package.json").read_text(encoding="utf-8")
    main_ts = Path("frontend/src/main.ts").read_text(encoding="utf-8")

    assert '"vite"' in package_json
    assert '"vue"' in package_json
    assert '"element-plus"' in package_json
    assert '"lucide-vue-next"' in package_json
    assert '"@amap/amap-jsapi-loader"' in package_json
    assert "createApp" in main_ts
    assert "ElementPlus" in main_ts


def test_frontend_uses_product_workspace_layout():
    app_vue = Path("frontend/src/App.vue").read_text(encoding="utf-8")
    composer_vue = Path("frontend/src/components/PlannerComposer.vue").read_text(encoding="utf-8")
    results_vue = Path("frontend/src/components/PlannerResults.vue").read_text(encoding="utf-8")
    map_vue = Path("frontend/src/components/AmapRoutePanel.vue").read_text(encoding="utf-8")

    assert "app-header" in app_vue
    assert "composer-card" in composer_vue
    assert "result-workspace" in results_vue
    assert "summary-strip" in results_vue
    assert "route-planner-layout" in results_vue
    assert "AmapRoutePanel" in results_vue
    assert "AMap.Geocoder" in map_vue
    assert "AMap.Driving" in map_vue
    assert "resolveDrivingSegment" in map_vue
    assert "geocodeMatchesCity" in map_vue
    assert "isLngLat(point.lnglat)" in map_vue


def test_frontend_shows_llm_generation_progress():
    app_vue = Path("frontend/src/App.vue").read_text(encoding="utf-8")
    results_vue = Path("frontend/src/components/PlannerResults.vue").read_text(encoding="utf-8")

    assert "模型生成过程" in results_vue
    assert "DeepSeek" in results_vue
    assert "LLMNeSy" in results_vue
    assert "解析需求" in app_vue
    assert "检索交通与本地数据" in app_vue
    assert "等待完整结果" in app_vue
    assert "window.setInterval(advanceProgress, 12000)" in app_vue
    assert "第 {{ day.day }} 天" not in results_vue


def test_frontend_adapts_flat_itinerary_response_shape():
    results_vue = Path("frontend/src/components/PlannerResults.vue").read_text(encoding="utf-8")
    planner_ts = Path("frontend/src/services/planner.ts").read_text(encoding="utf-8")

    assert "normalizeItineraryDays" in results_vue
    assert "FlatPlanActivity" in planner_ts
    assert "TrainID" in planner_ts
    assert "seat_label" in planner_ts
    assert "ticket_left" in planner_ts
    assert "recommended_food" in planner_ts
    assert "accommodation" in results_vue
    assert "推荐" in results_vue
    assert "activityCostText" in results_vue
    assert "intercity_reference" in results_vue
    assert "activityLngLat" in results_vue
    assert "amap_poi" in planner_ts


def test_frontend_results_are_api_driven_not_demo_static():
    app_vue = Path("frontend/src/App.vue").read_text(encoding="utf-8")
    results_vue = Path("frontend/src/components/PlannerResults.vue").read_text(encoding="utf-8")
    planner_ts = Path("frontend/src/services/planner.ts").read_text(encoding="utf-8")

    assert "requestPlan(payload)" in app_vue
    assert 'fetch("/api/plan"' in planner_ts
    assert 'fetch("/api/health"' in planner_ts
    assert "requestRuntimeHealth" in app_vue
    assert "demoResponse" not in app_vue
    assert "demoPayload" not in app_vue
    assert "demoResponse" not in results_vue
    assert "empty-state" in results_vue


def test_frontend_uses_compact_desktop_density():
    styles_css = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    results_vue = Path("frontend/src/components/PlannerResults.vue").read_text(encoding="utf-8")

    assert "--app-scale" in styles_css
    assert "height: calc((100vh / var(--app-scale)) - 118px)" in styles_css
    assert "overflow: hidden" in styles_css
    assert "flex: 1 1 auto" in styles_css
    assert "overflow-y: auto" in styles_css
    assert "route-map-panel" in styles_css
    assert "route-detail-panel" in styles_css
    assert "buildDayRoutePoints" in results_vue
    assert "width: min(1880px" in styles_css
    assert "grid-template-columns: minmax(300px, 450px)" in styles_css
    assert "route-content-grid" in styles_css
    assert "route-intel-panel" in styles_css
    assert "minmax(280px, 0.58fr)" in styles_css


def test_frontend_amap_env_is_documented():
    env_text = Path(".env").read_text(encoding="utf-8")

    assert "VITE_AMAP_API_KEY=91fc8915faa9ede9655b9be2d25e4f43" in env_text
    assert "VITE_AMAP_SECURITY_CODE=3a1011379c1da036ff9d07a91e516406" in env_text
    assert "AMAP_WEB_SERVICE_KEY=" in env_text
    assert "AMAP_WEB_SERVICE_KEY=91fc8915faa9ede9655b9be2d25e4f43" not in env_text


def test_frontend_composer_uses_compact_field_grid():
    styles_css = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    composer_vue = Path("frontend/src/components/PlannerComposer.vue").read_text(encoding="utf-8")

    assert "compact-control-grid" in composer_vue
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in styles_css


def test_frontend_composer_splits_joined_known_target_cities():
    composer_vue = Path("frontend/src/components/PlannerComposer.vue").read_text(encoding="utf-8")

    assert "knownTravelCityNames" in composer_vue
    assert '"桂林"' in composer_vue
    assert '"阳朔"' in composer_vue
    assert "normalized.includes(city)" in composer_vue
    assert "normalized.indexOf(left) - normalized.indexOf(right)" in composer_vue


def test_frontend_result_action_buttons_have_handlers():
    results_vue = Path("frontend/src/components/PlannerResults.vue").read_text(encoding="utf-8")

    assert "downloadItinerary" in results_vue
    assert "shareItinerary" in results_vue
    assert "saveItinerary" in results_vue
    assert "json-panel" not in results_vue
    assert "copyJson" not in results_vue
    assert "localStorage.setItem" in results_vue
    assert "navigator.share" in results_vue
    assert "navigator.clipboard.writeText" in results_vue


def test_frontend_overview_budget_sums_all_days():
    results_vue = Path("frontend/src/components/PlannerResults.vue").read_text(encoding="utf-8")

    assert "sumBudgetItems" in results_vue
    assert "itinerary.value.reduce((sum, day) => sum + budgetTotal(day), 0)" in results_vue
    assert "预算按全部天数汇总" in results_vue
    assert 'ref<number | "overview">("overview")' in results_vue


def test_frontend_shows_realtime_guides_and_spot_detail():
    results_vue = Path("frontend/src/components/PlannerResults.vue").read_text(encoding="utf-8")
    map_vue = Path("frontend/src/components/AmapRoutePanel.vue").read_text(encoding="utf-8")
    planner_ts = Path("frontend/src/services/planner.ts").read_text(encoding="utf-8")

    assert "RealtimeEvidence" in planner_ts
    assert "realtimeEvidence" in results_vue
    assert "热门攻略" in results_vue
    assert "activePlaceGuide" in results_vue
    assert "handleMapPointSelect" in results_vue
    assert "focusActivePoint" in map_vue
    assert "setZoomAndCenter(15" in map_vue


def test_frontend_exposes_realtime_toggle_dates_and_validation_dialog():
    app_vue = Path("frontend/src/App.vue").read_text(encoding="utf-8")
    composer_vue = Path("frontend/src/components/PlannerComposer.vue").read_text(encoding="utf-8")
    results_vue = Path("frontend/src/components/PlannerResults.vue").read_text(encoding="utf-8")
    planner_ts = Path("frontend/src/services/planner.ts").read_text(encoding="utf-8")

    assert ':runtime-health="runtimeHealth"' in app_vue
    assert "use_realtime" in planner_ts
    assert "realtime-control" in composer_vue
    assert "TAVILY_REAL_TIME_ENABLED=true" in composer_vue
    assert "defaultDepartureDate" in composer_vue
    assert "defaultReturnDate" in composer_vue
    assert "ensureFormDates" in composer_vue
    assert ':clearable="false"' in composer_vue
    assert "validateForm" in composer_vue
    assert "validation-dialog" in composer_vue
    assert "tabDateLabel" in results_vue
    assert "dayDateText" in results_vue


def test_frontend_composer_controls_are_interactive():
    composer_vue = Path("frontend/src/components/PlannerComposer.vue").read_text(encoding="utf-8")

    assert "togglePreference" in composer_vue
    assert "selectBudget" in composer_vue
    assert "budgetOptions" in composer_vue
    assert "@click=\"togglePreference(item)\"" in composer_vue
    assert "@click=\"selectBudget(option)\"" in composer_vue


def test_frontend_header_buttons_are_interactive():
    app_vue = Path("frontend/src/App.vue").read_text(encoding="utf-8")

    assert "toggleTheme" in app_vue
    assert "openDocs" in app_vue
    assert "toggleCoachMenu" in app_vue
    assert "@click=\"toggleTheme\"" in app_vue
    assert "@click=\"openDocs\"" in app_vue
    assert "@click=\"toggleCoachMenu\"" in app_vue


def test_frontend_conversation_workbench_contract():
    app_vue = Path("frontend/src/App.vue").read_text(encoding="utf-8")
    planner_ts = Path("frontend/src/services/planner.ts").read_text(encoding="utf-8")
    styles_css = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    for helper in [
        "requestConversations",
        "createConversation",
        "requestConversationDetail",
        "sendConversationMessage",
        "generateConversationPlan",
        "saveManualPlanEdit",
        "restorePlanVersion",
        "archiveConversation",
        "restoreConversation",
        "requestRecommendedPlans",
        "openRecommendedPlan",
    ]:
        assert helper in planner_ts

    assert 'type AppMode = "empty_chat" | "plan_workspace"' in app_vue
    assert "ConversationSidebar" in app_vue
    assert "TravelChatPanel" in app_vue
    assert "RecommendedPlans" in app_vue
    assert "PlanVersionTimeline" in app_vue
    assert "PlanWorkspace" in app_vue
    assert "DailyItineraryEditor" in Path("frontend/src/components/PlanWorkspace.vue").read_text(encoding="utf-8")
    assert "conversation-workbench empty-chat" in app_vue
    assert "conversation-workbench plan-workspace-grid" in app_vue
    assert "planningChecklist" in app_vue
    assert "generatedPlanCard" in app_vue
    assert "mobilePanel" in app_vue
    assert "mobile-workbench-tabs" in app_vue
    assert "legacy-plan-panel" in app_vue
    assert ".conversation-workbench.empty-chat" in styles_css
    assert ".conversation-workbench.plan-workspace-grid" in styles_css
    assert ".mobile-workbench-tabs" in styles_css


def test_frontend_exposes_form_based_manual_editor():
    editor_vue = Path("frontend/src/components/DailyItineraryEditor.vue").read_text(encoding="utf-8")
    workspace_vue = Path("frontend/src/components/PlanWorkspace.vue").read_text(encoding="utf-8")
    planner_ts = Path("frontend/src/services/planner.ts").read_text(encoding="utf-8")
    styles_css = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "DailyItineraryEditor" in workspace_vue
    assert "表单化编辑" in editor_vue
    assert "保存新版" in editor_vue
    assert "添加天数" in editor_vue
    assert "添加活动" in editor_vue
    assert "validation_override" in editor_vue
    assert "serverWarnings" in editor_vue
    assert "version.validation_warnings" in Path("frontend/src/components/PlanVersionTimeline.vue").read_text(encoding="utf-8")
    assert "ManualPlanEditRequest" in planner_ts
    assert "validation_warnings" in planner_ts
    assert "/manual-edit" in planner_ts
    assert ".daily-itinerary-editor" in styles_css
    assert ".activity-editor-row" in styles_css


def test_frontend_initial_chat_clarifies_before_generation():
    app_vue = Path("frontend/src/App.vue").read_text(encoding="utf-8")
    chat_vue = Path("frontend/src/components/TravelChatPanel.vue").read_text(encoding="utf-8")
    planner_ts = Path("frontend/src/services/planner.ts").read_text(encoding="utf-8")

    assert 'mode === "empty_chat" ? "发送" : "提交修改"' in chat_vue
    assert "规划清单确认" in chat_vue
    assert "确认清单并生成攻略" in chat_vue
    assert "攻略已生成" in chat_vue
    assert "查看并编辑规划" in chat_vue
    assert "checklistVisible" in chat_vue
    assert "generatedCard" in chat_vue
    assert "confirmGenerate" in chat_vue
    assert "openGeneratedPlan" in chat_vue
    assert "generateConversationPlan(currentConversation.value.id, payload)" in app_vue
    assert "shouldShowChecklist" in app_vue
    assert "/generate" in planner_ts


def test_backend_exposes_manual_edit_endpoint_contract():
    main_py = Path("app/main.py").read_text(encoding="utf-8")
    schemas_py = Path("app/schemas.py").read_text(encoding="utf-8")

    assert "ConversationManualEditRequest" in schemas_py
    assert '"/api/conversations/{conversation_id}/manual-edit"' in main_py
    assert 'source="manual_edit"' in main_py
    assert "VERSION_CONFLICT" in main_py
    assert "PLAN_VALIDATION_FAILED" in main_py
