from pathlib import Path


def test_frontend_files_exist():
    for relative_path in [
        Path("frontend/index.html"),
        Path("frontend/src/main.ts"),
        Path("frontend/src/App.vue"),
        Path("frontend/src/components/PlannerComposer.vue"),
        Path("frontend/src/components/PlannerResults.vue"),
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
    assert "createApp" in main_ts
    assert "ElementPlus" in main_ts


def test_frontend_uses_product_workspace_layout():
    app_vue = Path("frontend/src/App.vue").read_text(encoding="utf-8")
    composer_vue = Path("frontend/src/components/PlannerComposer.vue").read_text(encoding="utf-8")
    results_vue = Path("frontend/src/components/PlannerResults.vue").read_text(encoding="utf-8")

    assert "app-header" in app_vue
    assert "composer-card" in composer_vue
    assert "result-workspace" in results_vue
    assert "summary-strip" in results_vue


def test_frontend_shows_llm_generation_progress():
    results_vue = Path("frontend/src/components/PlannerResults.vue").read_text(encoding="utf-8")

    assert "模型生成过程" in results_vue
    assert "DeepSeek" in results_vue
    assert "LLMNeSy" in results_vue
    assert "当前生成" in results_vue
    assert "等待生成" in results_vue


def test_frontend_adapts_flat_itinerary_response_shape():
    results_vue = Path("frontend/src/components/PlannerResults.vue").read_text(encoding="utf-8")
    planner_ts = Path("frontend/src/services/planner.ts").read_text(encoding="utf-8")

    assert "normalizeItineraryDays" in results_vue
    assert "FlatPlanActivity" in planner_ts
    assert "TrainID" in planner_ts
    assert "recommended_food" in planner_ts
    assert "accommodation" in results_vue
    assert "推荐" in results_vue


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

    assert "--app-scale" in styles_css
    assert "min-height: 164px" in styles_css
    assert "width: min(1760px" in styles_css
    assert "grid-template-columns: minmax(320px, 500px)" in styles_css


def test_frontend_result_action_buttons_have_handlers():
    results_vue = Path("frontend/src/components/PlannerResults.vue").read_text(encoding="utf-8")

    assert "downloadItinerary" in results_vue
    assert "shareItinerary" in results_vue
    assert "saveItinerary" in results_vue
    assert "copyJson" in results_vue
    assert "localStorage.setItem" in results_vue
    assert "navigator.share" in results_vue
    assert "navigator.clipboard.writeText" in results_vue


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
