<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import AMapLoader from "@amap/amap-jsapi-loader";
import { MapPin } from "lucide-vue-next";
import type { RoutePoint } from "../types/route";

interface ResolvedPoint extends RoutePoint {
  lnglat: [number, number];
}

const props = defineProps<{
  points: RoutePoint[];
  selectedDay: number | "overview";
  activePointId: string;
}>();

const emit = defineEmits<{
  "select-point": [id: string];
}>();

const mapEl = ref<HTMLDivElement | null>(null);
const mapStatus = ref<"idle" | "loading" | "ready" | "error">("idle");
const mapError = ref("");
const unresolvedCount = ref(0);
const fallbackRouteCount = ref(0);

let amapApi: any;
let mapInstance: any;
let geocoder: any;
let driving: any;
let routeOverlays: any[] = [];
let markers: Array<{ marker: any; point: ResolvedPoint }> = [];
let loadToken = 0;
const geocodeCache = new Map<string, [number, number] | null>();
const routeCache = new Map<string, [number, number][] | null>();

const CITY_FALLBACK_COORDS: Record<string, [number, number]> = {
  上海: [121.4737, 31.2304],
  苏州: [120.5853, 31.2989],
  南京: [118.7969, 32.0603],
  杭州: [120.1551, 30.2741],
  成都: [104.0665, 30.5723],
  重庆: [106.5516, 29.563],
  西安: [108.9398, 34.3416],
  厦门: [118.0894, 24.4798],
  桂林: [110.2902, 25.2736],
  阳朔: [110.4963, 24.7785],
  北京: [116.4074, 39.9042],
};

const PLACE_FALLBACK_COORDS: Array<{ keywords: string[]; lnglat: [number, number] }> = [
  { keywords: ["上海站"], lnglat: [121.4557, 31.2496] },
  { keywords: ["苏州站"], lnglat: [120.6068, 31.3314] },
  { keywords: ["拙政园"], lnglat: [120.6299, 31.3244] },
  { keywords: ["寒山寺"], lnglat: [120.5618, 31.3146] },
  { keywords: ["王氏林记", "双塔"], lnglat: [120.6268, 31.3092] },
  { keywords: ["苏州花惜美拾", "黑曜吴江"], lnglat: [120.6464, 31.16] },
  { keywords: ["狮子林"], lnglat: [120.6266, 31.3266] },
  { keywords: ["苏州博物馆"], lnglat: [120.6274, 31.3247] },
  { keywords: ["平江路"], lnglat: [120.632, 31.3157] },
  { keywords: ["山塘街"], lnglat: [120.5889, 31.3208] },
  { keywords: ["留园"], lnglat: [120.5824, 31.3175] },
  { keywords: ["虎丘"], lnglat: [120.574, 31.3383] },
  { keywords: ["金鸡湖"], lnglat: [120.7068, 31.3041] },
  { keywords: ["东方之门"], lnglat: [120.6794, 31.3175] },
];

const visiblePoints = computed(() => {
  if (props.selectedDay === "overview") return props.points;
  return props.points.filter((point) => point.day === props.selectedDay);
});

const mapTitle = computed(() => (props.selectedDay === "overview" ? "全部路线地图" : `第 ${props.selectedDay} 天路线地图`));

watch(
  () => [props.points, props.selectedDay] as const,
  () => {
    void renderRoute();
  },
  { deep: true, immediate: true },
);

watch(
  () => props.activePointId,
  () => {
    updateMarkerState();
  },
);

async function ensureMap() {
  if (mapInstance) return true;
  const apiKey = import.meta.env.VITE_AMAP_API_KEY;
  const securityCode = import.meta.env.VITE_AMAP_SECURITY_CODE;
  if (!apiKey) {
    mapStatus.value = "error";
    mapError.value = "缺少 VITE_AMAP_API_KEY，地图暂不可用。";
    return false;
  }

  await nextTick();
  if (!mapEl.value) return false;

  mapStatus.value = "loading";
  mapError.value = "";
  try {
    if (securityCode) {
      window._AMapSecurityConfig = { securityJsCode: securityCode };
    }
    amapApi = await AMapLoader.load({
      key: apiKey,
      version: "2.0",
      plugins: ["AMap.Geocoder", "AMap.Scale", "AMap.ToolBar", "AMap.Driving"],
    });
    mapInstance = new amapApi.Map(mapEl.value, {
      zoom: 10,
      viewMode: "2D",
      mapStyle: "amap://styles/normal",
    });
    mapInstance.addControl(new amapApi.Scale());
    mapInstance.addControl(new amapApi.ToolBar({ position: { right: "16px", top: "16px" } }));
    geocoder = new amapApi.Geocoder({ city: "全国" });
    driving = new amapApi.Driving({ policy: amapApi.DrivingPolicy.LEAST_TIME });
    mapStatus.value = "ready";
    return true;
  } catch (error) {
    mapStatus.value = "error";
    mapError.value = error instanceof Error ? error.message : "高德地图加载失败。";
    return false;
  }
}

async function renderRoute() {
  const token = ++loadToken;
  const ready = await ensureMap();
  if (!ready || !mapInstance || !amapApi) return;
  clearOverlays();

  if (!visiblePoints.value.length) {
    unresolvedCount.value = 0;
    fallbackRouteCount.value = 0;
    mapInstance.setZoomAndCenter(10, CITY_FALLBACK_COORDS["苏州"]);
    return;
  }

  const resolved = (await Promise.all(visiblePoints.value.map((point, index) => resolvePoint(point, index)))).filter(
    (point): point is ResolvedPoint => Boolean(point),
  );
  if (token !== loadToken) return;

  unresolvedCount.value = visiblePoints.value.length - resolved.length;
  markers = resolved.map((point) => {
    const marker = new amapApi.Marker({
      position: point.lnglat,
      title: point.name,
      anchor: "center",
      content: markerContent(point, point.id === props.activePointId),
    });
    marker.on("click", () => emit("select-point", point.id));
    mapInstance.add(marker);
    return { marker, point };
  });

  const path = resolved.map((point) => point.lnglat);
  let routeFallbacks = 0;
  const shouldDrawPath = props.selectedDay !== "overview" && path.length >= 2;
  if (shouldDrawPath) {
    for (let index = 0; index < resolved.length - 1; index += 1) {
      const segmentPath = await resolveDrivingSegment(resolved[index], resolved[index + 1]);
      if (token !== loadToken) return;
      if (segmentPath?.length) {
        addRouteLine(segmentPath, false);
      } else {
        routeFallbacks += 1;
        addRouteLine([resolved[index].lnglat, resolved[index + 1].lnglat], true);
      }
    }
  }
  fallbackRouteCount.value = routeFallbacks;

  if (path.length) {
    mapInstance.setFitView(markers.map((item) => item.marker).concat(routeOverlays), false, [42, 42, 42, 42]);
  }
  updateMarkerState();
}

async function resolveDrivingSegment(start: ResolvedPoint, end: ResolvedPoint): Promise<[number, number][] | null> {
  const cacheKey = `${start.lnglat.join(",")}-${end.lnglat.join(",")}`;
  if (routeCache.has(cacheKey)) return routeCache.get(cacheKey) || null;
  const path = await planDrivingRoute(start.lnglat, end.lnglat);
  routeCache.set(cacheKey, path);
  return path;
}

function planDrivingRoute(start: [number, number], end: [number, number]): Promise<[number, number][] | null> {
  return new Promise((resolve) => {
    if (!driving) {
      resolve(null);
      return;
    }
    let settled = false;
    const finish = (value: [number, number][] | null) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timer);
      resolve(value);
    };
    const timer = window.setTimeout(() => finish(null), 3800);
    driving.search(start, end, (status: string, result: any) => {
      const steps = result?.routes?.[0]?.steps;
      if (status !== "complete" || !Array.isArray(steps)) {
        finish(null);
        return;
      }
      const routePath = steps.flatMap((step: any) =>
        Array.isArray(step.path)
          ? step.path
              .map((point: any) => [Number(point.lng), Number(point.lat)] as [number, number])
              .filter(([lng, lat]: [number, number]) => Number.isFinite(lng) && Number.isFinite(lat))
          : [],
      );
      finish(routePath.length >= 2 ? routePath : null);
    });
  });
}

function addRouteLine(path: [number, number][], isFallback: boolean) {
  const line = new amapApi.Polyline({
    path,
    strokeColor: isFallback ? "#a05a18" : "#0b765f",
    strokeWeight: isFallback ? 4 : 5,
    strokeOpacity: isFallback ? 0.72 : 0.86,
    strokeStyle: isFallback ? "dashed" : "solid",
    lineJoin: "round",
    lineCap: "round",
    zIndex: isFallback ? 48 : 50,
  });
  mapInstance.add(line);
  routeOverlays.push(line);
}

async function resolvePoint(point: RoutePoint, index: number): Promise<ResolvedPoint | null> {
  const knownCoordinate = fallbackCoordinate(point, index, false);
  if (knownCoordinate) return { ...point, lnglat: knownCoordinate };
  const geocoded = await resolveByGeocoder(point);
  const fallback = geocoded || fallbackCoordinate(point, index, true);
  return fallback ? { ...point, lnglat: fallback } : null;
}

async function resolveByGeocoder(point: RoutePoint) {
  const queries = [point.city && point.name ? `${point.city}${point.name}` : undefined, point.name].filter(
    (item): item is string => Boolean(item?.trim()),
  );
  for (const query of queries) {
    const cached = geocodeCache.get(query);
    if (cached) return cached;
    if (cached === null) continue;
    const lnglat = await geocode(query);
    geocodeCache.set(query, lnglat);
    if (lnglat) return lnglat;
  }
  return null;
}

function geocode(query: string): Promise<[number, number] | null> {
  return new Promise((resolve) => {
    if (!geocoder) {
      resolve(null);
      return;
    }
    let settled = false;
    const finish = (value: [number, number] | null) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timer);
      resolve(value);
    };
    const timer = window.setTimeout(() => finish(null), 1800);
    geocoder.getLocation(query, (status: string, result: any) => {
      const location = result?.geocodes?.[0]?.location;
      if (status === "complete" && location) {
        finish([Number(location.lng), Number(location.lat)]);
        return;
      }
      finish(null);
    });
  });
}

function fallbackCoordinate(point: RoutePoint, index: number, allowCityScatter: boolean): [number, number] | null {
  const compactName = compact(point.name);
  const placeMatch = PLACE_FALLBACK_COORDS.find((entry) => entry.keywords.some((keyword) => compactName.includes(compact(keyword))));
  if (placeMatch) return placeMatch.lnglat;

  if (!allowCityScatter) return null;
  const city = cityFromPoint(point);
  if (!city) return null;
  const center = CITY_FALLBACK_COORDS[city];
  const angle = (index % 8) * (Math.PI / 4);
  const radius = 0.012 + Math.floor(index / 8) * 0.008;
  return [Number((center[0] + Math.cos(angle) * radius).toFixed(6)), Number((center[1] + Math.sin(angle) * radius).toFixed(6))];
}

function cityFromPoint(point: RoutePoint) {
  const raw = `${point.city || ""}${point.name || ""}`;
  return Object.keys(CITY_FALLBACK_COORDS).find((city) => raw.includes(city)) || "苏州";
}

function compact(value: string) {
  return value.replace(/[()\s（）·\-]/g, "").toLowerCase();
}

function markerContent(point: RoutePoint, active: boolean) {
  const typeClass = point.type ? ` is-${point.type}` : "";
  return `<button class="amap-route-marker${active ? " active" : ""}${typeClass}" type="button" aria-label="${point.name}">
    <span>${point.order}</span>
  </button>`;
}

function updateMarkerState() {
  markers.forEach(({ marker, point }) => {
    marker.setContent(markerContent(point, point.id === props.activePointId));
  });
}

function clearOverlays() {
  if (!mapInstance) return;
  markers.forEach(({ marker }) => mapInstance.remove(marker));
  markers = [];
  routeOverlays.forEach((overlay) => mapInstance.remove(overlay));
  routeOverlays = [];
}

onBeforeUnmount(() => {
  clearOverlays();
  mapInstance?.destroy();
  mapInstance = null;
});

onMounted(() => {
  void renderRoute();
});
</script>

<template>
  <section class="route-map-panel" :aria-label="mapTitle">
    <div ref="mapEl" class="route-map-canvas" />
    <div v-if="mapStatus === 'loading'" class="map-state">
      <MapPin :size="24" />
      <span>地图加载中</span>
    </div>
    <div v-else-if="mapStatus === 'error'" class="map-state is-error">
      <MapPin :size="24" />
      <strong>地图暂不可用</strong>
      <span>{{ mapError }}</span>
    </div>
    <div class="map-overlay">
      <span>{{ mapTitle }}</span>
      <small v-if="unresolvedCount">有 {{ unresolvedCount }} 个地点未定位</small>
      <small v-if="fallbackRouteCount">有 {{ fallbackRouteCount }} 段路线使用降级连线</small>
    </div>
    <div class="map-legend" aria-label="地图图例">
      <span><i class="is-train" />交通</span>
      <span><i class="is-attraction" />景点</span>
      <span><i class="is-restaurant" />餐饮</span>
      <span><i class="is-accommodation" />住宿</span>
    </div>
  </section>
</template>
