const form = document.querySelector("#plan-form");
const submitButton = document.querySelector("#submit-button");
const statusPill = document.querySelector("#status-pill");
const message = document.querySelector("#message");
const itinerary = document.querySelector("#itinerary");
const jsonOutput = document.querySelector("#json-output");

const optionalNumber = (formData, key) => {
  const value = formData.get(key);
  if (!value) return undefined;
  return Number(value);
};

const optionalText = (formData, key) => {
  const value = String(formData.get(key) || "").trim();
  return value || undefined;
};

const setStatus = (label, mode = "") => {
  statusPill.textContent = label;
  statusPill.className = `status-pill ${mode}`.trim();
};

const showMessage = (text, mode = "is-muted") => {
  message.textContent = text;
  message.className = `message ${mode}`.trim();
};

const renderJson = (payload) => {
  jsonOutput.hidden = false;
  jsonOutput.textContent = JSON.stringify(payload, null, 2);
};

const renderItinerary = (plan) => {
  itinerary.innerHTML = "";
  const days = Array.isArray(plan?.itinerary) ? plan.itinerary : [];
  if (!days.length) return;

  const fragment = document.createDocumentFragment();
  days.forEach((day, index) => {
    const card = document.createElement("article");
    card.className = "day-card";

    const title = document.createElement("h3");
    title.textContent = `第 ${day.day || index + 1} 天`;
    card.append(title);

    const activities = Array.isArray(day.activities) ? day.activities : [];
    activities.forEach((activity) => {
      const row = document.createElement("div");
      row.className = "activity";

      const time = document.createElement("div");
      time.className = "activity-time";
      time.textContent = `${activity.start_time || "--:--"} - ${activity.end_time || "--:--"}`;

      const body = document.createElement("div");
      const place = activity.position || activity.end || activity.start || "未命名活动";
      const cost = activity.cost === undefined ? "" : ` · ¥${activity.cost}`;
      body.innerHTML = `
        <p class="activity-title"></p>
        <p class="activity-meta"></p>
      `;
      body.querySelector(".activity-title").textContent = place;
      body.querySelector(".activity-meta").textContent = `${activity.type || "activity"}${cost}`;

      row.append(time, body);
      card.append(row);
    });

    fragment.append(card);
  });
  itinerary.append(fragment);
};

const buildPayload = () => {
  const formData = new FormData(form);
  const payload = {
    query: optionalText(formData, "query"),
    start_city: optionalText(formData, "start_city"),
    target_city: optionalText(formData, "target_city"),
    days: optionalNumber(formData, "days"),
    people_number: optionalNumber(formData, "people_number"),
    budget: optionalNumber(formData, "budget"),
  };

  Object.keys(payload).forEach((key) => {
    if (payload[key] === undefined || payload[key] === "") {
      delete payload[key];
    }
  });
  return payload;
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = buildPayload();

  submitButton.disabled = true;
  setStatus("生成中");
  showMessage("正在调用 DeepSeek 和本地旅行数据生成行程...");
  itinerary.innerHTML = "";
  jsonOutput.hidden = true;

  try {
    const response = await fetch("/api/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    renderJson(data);

    if (!response.ok || data.success === false) {
      setStatus("失败", "is-error");
      showMessage(data.error?.message || "生成失败，请检查输入和后端配置。", "is-error");
      return;
    }

    setStatus("完成", "is-ok");
    showMessage("行程已生成。下方是可读行程卡片，完整 JSON 保留在末尾。", "is-muted");
    renderItinerary(data.plan);
  } catch (error) {
    setStatus("失败", "is-error");
    showMessage(`请求失败：${error.message}`, "is-error");
  } finally {
    submitButton.disabled = false;
  }
});
