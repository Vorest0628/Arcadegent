import type { ArcadeDetail, PagedArcades, RegionItem } from "../types";

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

