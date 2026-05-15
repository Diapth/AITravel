# ChinaTravel Vite Vue Workbench Spec

## Goal

Refactor the frontend into a Vite + Vue 3 travel planning workbench that feels like a production product UI and keeps users informed while the LLM planner is running.

## Confirmed Direction

- Use Vite, Vue 3, TypeScript, Element Plus, and lucide-vue-next.
- Keep FastAPI serving the built frontend from `frontend/`.
- Preserve the existing `POST /api/plan` payload and response contract.
- Use Chinese UI copy throughout the product surface.
- Use a refined travel operations desk style: warm rice-paper background, porcelain panels, jade green primary color, cinnabar/amber accents, charcoal text, subtle route/map motifs, and compact dashboard density.

## User Experience

- Left side: sticky input composer titled `旅行需求` with natural language textarea, optional structured fields, example route chips, and primary `生成行程` button.
- Right side: `规划结果` workspace with status chip, summary strip, visible model generation process, itinerary cards, and collapsible JSON output.
- During generation, show that DeepSeek/LLMNeSy is working instead of leaving the user waiting.
- Model progress is day-based:
  - Already generated days are displayed as readable itinerary cards.
  - The current day shows active progress and partial/skeleton content.
  - Future days show queued status.
- The final API response replaces the simulated progress with the real structured plan.

## Non-Goals

- Do not change the backend planner algorithm.
- Do not add a streaming backend endpoint in this pass.
- Do not remove existing `.env` or local database behavior.
- Do not introduce route navigation or auth.

