import { createApp } from "vue";
import ElementPlus from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import "element-plus/dist/index.css";
import "element-plus/theme-chalk/dark/css-vars.css";
import "vue-element-plus-x/styles/index.css";
import App from "./App.vue";

/* Design tokens & framework overrides */
import "./styles/tokens.css";
import "./styles/element-overrides.css";

/* Base styles */
import "./styles/base.css";
import "./styles/animations.css";

/* Component-area styles */
import "./styles/header.css";
import "./styles/chat.css";
import "./styles/sidebar.css";
import "./styles/recommendations.css";
import "./styles/workspace.css";
import "./styles/editor.css";
import "./styles/planner.css";

/* Responsive & dark mode (must come last) */
import "./styles/responsive.css";
import "./styles/dark.css";

const app = createApp(App);

app.use(ElementPlus, { locale: zhCn });
app.mount("#app");
