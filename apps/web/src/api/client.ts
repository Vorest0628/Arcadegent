import type {
  ArcadeDetail,
  ChatRequest,
  ChatResponse,
  ChatSessionDetail,
  ChatSessionSummary,
  PagedArcades,
  RegionItem
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

function buildUrl(path: string, query?: Record<string, string | number | boolean | undefined | null>): string {
  const url = new URL(path, API_BASE);
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && `${value}`.length > 0) {
        url.searchParams.set(key, String(value));
      }
    });
  }
  return url.toString();
}

async function fetchJson<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${url}`);
  }
  return (await resp.json()) as T;
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  const resp = await fetch(buildUrl(path), {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${path}`);
  }
  return (await resp.json()) as T;
}

async function deleteJson(path: string): Promise<void> {
  const resp = await fetch(buildUrl(path), { method: "DELETE" });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${path}`);
  }
}

export async function listArcades(params: {
  keyword?: string;
  province_code?: string;
  city_code?: string;
  county_code?: string;
  page?: number;
  page_size?: number;
}): Promise<PagedArcades> {
  return fetchJson<PagedArcades>(buildUrl("/api/v1/arcades", params));
}

export async function getArcadeDetail(sourceId: number): Promise<ArcadeDetail> {
  return fetchJson<ArcadeDetail>(buildUrl(`/api/v1/arcades/${sourceId}`));
}

export async function listProvinces(): Promise<RegionItem[]> {
  return fetchJson<RegionItem[]>(buildUrl("/api/v1/regions/provinces"));
}

export async function listCities(provinceCode: string): Promise<RegionItem[]> {
  return fetchJson<RegionItem[]>(buildUrl("/api/v1/regions/cities", { province_code: provinceCode }));
}

export async function listCounties(cityCode: string): Promise<RegionItem[]> {
  return fetchJson<RegionItem[]>(buildUrl("/api/v1/regions/counties", { city_code: cityCode }));
}

export async function sendChat(payload: ChatRequest): Promise<ChatResponse> {
  return postJson<ChatResponse>("/api/chat", payload);
}

export function buildChatStreamUrl(sessionId: string, lastEventId?: number): string {
  return buildUrl(`/api/stream/${encodeURIComponent(sessionId)}`, {
    last_event_id: typeof lastEventId === "number" ? lastEventId : undefined
  });
}

export async function listChatSessions(limit = 40): Promise<ChatSessionSummary[]> {
  return fetchJson<ChatSessionSummary[]>(buildUrl("/api/v1/chat/sessions", { limit }));
}

export async function getChatSession(sessionId: string): Promise<ChatSessionDetail> {
  return fetchJson<ChatSessionDetail>(buildUrl(`/api/v1/chat/sessions/${encodeURIComponent(sessionId)}`));
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  return deleteJson(`/api/v1/chat/sessions/${encodeURIComponent(sessionId)}`);
}
