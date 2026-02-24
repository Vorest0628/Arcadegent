-- W1 Draft freeze: initial schema for arcade locator.
-- Compatible with shops_detail.jsonl payload and ETL outputs.

create extension if not exists postgis;

create table if not exists arcade_shops (
  id bigserial primary key,
  source text not null,
  source_id bigint not null,
  source_url text not null,
  name text not null,
  name_pinyin text,
  address text,
  transport text,
  url text,
  comment text,
  province_code varchar(12),
  province_name text,
  city_code varchar(12),
  city_name text,
  county_code varchar(12),
  county_name text,
  longitude_gcj02 double precision,
  latitude_gcj02 double precision,
  longitude_wgs84 double precision,
  latitude_wgs84 double precision,
  geo_wgs84 geography(Point, 4326),
  geo_source text,
  geo_precision text,
  status text,
  type text,
  pay_type text,
  locked text,
  ea_status text,
  price text,
  start_time text,
  end_time text,
  fav_count int,
  created_at_src text,
  updated_at_src text,
  option1 jsonb,
  option2 jsonb,
  option3 jsonb,
  option4 jsonb,
  option5 jsonb,
  collab boolean,
  image_thumb jsonb,
  events jsonb not null default '[]'::jsonb,
  raw jsonb not null,
  ingest_batch_id text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (source, source_id)
);

create table if not exists arcade_titles (
  id bigserial primary key,
  source text not null,
  source_id bigint not null,
  arcade_item_id bigint,
  title_id text,
  title_name text,
  quantity int,
  version text,
  coin text,
  eacoin text,
  comment text,
  raw jsonb not null,
  ingest_batch_id text not null
);

create table if not exists ingest_runs (
  batch_id text primary key,
  source text not null,
  started_at timestamptz,
  finished_at timestamptz,
  args jsonb not null,
  counts jsonb not null,
  failed_shop_ids jsonb not null,
  outputs jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_arcade_shops_geo_wgs84
  on arcade_shops using gist (geo_wgs84);

create index if not exists idx_arcade_shops_region
  on arcade_shops (province_code, city_code, county_code);

create index if not exists idx_arcade_shops_updated
  on arcade_shops (updated_at_src desc nulls last, source_id asc);

create index if not exists idx_arcade_shops_text
  on arcade_shops using gin (
    to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(address, ''))
  );

create index if not exists idx_arcade_titles_lookup
  on arcade_titles (source, source_id, title_id);

create or replace function search_nearby_arcades(
  p_lng double precision,
  p_lat double precision,
  p_radius_m int default 3000,
  p_limit int default 30
)
returns setof arcade_shops
language sql
stable
as $$
  select *
  from arcade_shops s
  where s.geo_wgs84 is not null
    and st_dwithin(
      s.geo_wgs84,
      st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography,
      p_radius_m
    )
  order by st_distance(
    s.geo_wgs84,
    st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography
  )
  limit p_limit;
$$;

