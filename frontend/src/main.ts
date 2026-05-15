import { createApp } from "vue";
import { ElDatePicker } from "element-plus/es/components/date-picker/index.mjs";
import { ElForm, ElFormItem } from "element-plus/es/components/form/index.mjs";
import { ElInput } from "element-plus/es/components/input/index.mjs";
import { ElInputNumber } from "element-plus/es/components/input-number/index.mjs";
import "element-plus/theme-chalk/base.css";
import "element-plus/theme-chalk/el-date-picker.css";
import "element-plus/theme-chalk/el-form.css";
import "element-plus/theme-chalk/el-input.css";
import "element-plus/theme-chalk/el-input-number.css";
import App from "./App.vue";
import "./styles.css";

const ElementPlusComponents = [ElDatePicker, ElForm, ElFormItem, ElInput, ElInputNumber];
const app = createApp(App);

ElementPlusComponents.forEach((component) => app.use(component));
app.mount("#app");
