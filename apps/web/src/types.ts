export type RegionItem = {
  code: string;
  name: string;
};

export type ArcadeSummary = {
  source: string;
  source_id: number;
  source_url: string;
  name: string;
  name_pinyin?: string | null;
  address?: string | null;
  transport?: string | null;
  province_code?: string | null;
  province_name?: string | null;
  city_code?: string | null;
  city_name?: string | null;
  county_code?: string | null;
  county_name?: string | null;
  status?: string | number | null;
  type?: string | number | null;
  pay_type?: string | number | null;
  locked?: string | number | null;
  ea_status?: string | number | null;
  price?: string | number | null;
  start_time?: string | number | null;
  end_time?: string | number | null;
  fav_count?: number | null;
  updated_at?: string | null;
  arcade_count: number;
};

export type ArcadeTitle = {
  id?: number | null;
  title_id?: string | number | null;
  title_name?: string | null;
  quantity?: number | null;
  version?: string | null;
  coin?: string | number | null;
  eacoin?: string | number | null;
  comment?: string | null;
};

export type ArcadeDetail = ArcadeSummary & {
  comment?: string | null;
  url?: string | null;
  image_thumb?: Record<string, unknown> | null;
  events: Array<Record<string, unknown>>;
  arcades: ArcadeTitle[];
  collab?: boolean | null;
};

export type PagedArcades = {
  items: ArcadeSummary[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

