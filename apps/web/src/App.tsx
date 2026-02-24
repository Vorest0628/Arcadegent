import { FormEvent, useEffect, useMemo, useState } from "react";
import { getArcadeDetail, listArcades, listCities, listCounties, listProvinces } from "./api/client";
import type { ArcadeDetail, ArcadeSummary, PagedArcades, RegionItem } from "./types";

function usePagedState(): [PagedArcades, (payload: PagedArcades) => void] {
  const [data, setData] = useState<PagedArcades>({
    items: [],
    page: 1,
    page_size: 20,
    total: 0,
    total_pages: 0
  });
  return [data, setData];
}

export function App() {
  const [provinces, setProvinces] = useState<RegionItem[]>([]);
  const [cities, setCities] = useState<RegionItem[]>([]);
  const [counties, setCounties] = useState<RegionItem[]>([]);
  const [keyword, setKeyword] = useState("");
  const [provinceCode, setProvinceCode] = useState("");
  const [cityCode, setCityCode] = useState("");
  const [countyCode, setCountyCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<ArcadeDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [paged, setPaged] = usePagedState();

  const pageSize = 20;

  useEffect(() => {
    void (async () => {
      const rows = await listProvinces();
      setProvinces(rows);
    })();
  }, []);

  useEffect(() => {
    if (!provinceCode) {
      setCities([]);
      setCityCode("");
      setCounties([]);
      setCountyCode("");
      return;
    }
    void (async () => {
      const rows = await listCities(provinceCode);
      setCities(rows);
      setCityCode("");
      setCounties([]);
      setCountyCode("");
    })();
  }, [provinceCode]);

  useEffect(() => {
    if (!cityCode) {
      setCounties([]);
      setCountyCode("");
      return;
    }
    void (async () => {
      const rows = await listCounties(cityCode);
      setCounties(rows);
      setCountyCode("");
    })();
  }, [cityCode]);

  async function runSearch(page = 1) {
    try {
      setLoading(true);
      setError("");
      const payload = await listArcades({
        keyword,
        province_code: provinceCode || undefined,
        city_code: cityCode || undefined,
        county_code: countyCode || undefined,
        page,
        page_size: pageSize
      });
      setPaged(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "查询失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void runSearch(1);
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await runSearch(1);
  }

  async function openDetail(item: ArcadeSummary) {
    setDetailLoading(true);
    try {
      const payload = await getArcadeDetail(item.source_id);
      setDetail(payload);
    } finally {
      setDetailLoading(false);
    }
  }

  const pageHint = useMemo(() => {
    if (paged.total <= 0) {
      return "无结果";
    }
    const start = (paged.page - 1) * paged.page_size + 1;
    const end = Math.min(paged.total, paged.page * paged.page_size);
    return `${start}-${end} / ${paged.total}`;
  }, [paged]);

  return (
    <div className="page">
      <header className="hero">
        <h1>Arcadegent Locator</h1>
        <p>按关键词与省市区检索机厅，查看门店详情与机台分布。</p>
      </header>

      <main className="layout">
        <section className="card controls">
          <form onSubmit={onSubmit} className="filter-grid">
            <label>
              关键词
              <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="如 maimai / 风云再起" />
            </label>
            <label>
              省份
              <select value={provinceCode} onChange={(e) => setProvinceCode(e.target.value)}>
                <option value="">全部</option>
                {provinces.map((row) => (
                  <option value={row.code} key={row.code}>
                    {row.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              城市
              <select value={cityCode} onChange={(e) => setCityCode(e.target.value)} disabled={!provinceCode}>
                <option value="">全部</option>
                {cities.map((row) => (
                  <option value={row.code} key={row.code}>
                    {row.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              区县
              <select value={countyCode} onChange={(e) => setCountyCode(e.target.value)} disabled={!cityCode}>
                <option value="">全部</option>
                {counties.map((row) => (
                  <option value={row.code} key={row.code}>
                    {row.name}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" disabled={loading}>
              {loading ? "检索中..." : "开始检索"}
            </button>
          </form>

          {error ? <div className="error">{error}</div> : null}

          <div className="list-header">
            <strong>检索结果</strong>
            <span>{pageHint}</span>
          </div>

          <ul className="result-list">
            {paged.items.map((item) => (
              <li key={item.source_id}>
                <button type="button" onClick={() => openDetail(item)}>
                  <h3>{item.name}</h3>
                  <p>{item.address || "暂无地址"}</p>
                  <small>
                    {item.province_name || "-"} / {item.city_name || "-"} / {item.county_name || "-"} · 机台{" "}
                    {item.arcade_count}
                  </small>
                </button>
              </li>
            ))}
          </ul>

          <div className="pager">
            <button
              type="button"
              disabled={paged.page <= 1 || loading}
              onClick={() => void runSearch(Math.max(1, paged.page - 1))}
            >
              上一页
            </button>
            <span>
              第 {paged.page} / {Math.max(1, paged.total_pages)} 页
            </span>
            <button
              type="button"
              disabled={paged.page >= paged.total_pages || loading || paged.total_pages === 0}
              onClick={() => void runSearch(paged.page + 1)}
            >
              下一页
            </button>
          </div>
        </section>

        <aside className="card detail">
          <div className="detail-head">
            <strong>门店详情</strong>
          </div>
          {detailLoading ? <p>加载详情中...</p> : null}
          {!detailLoading && !detail ? <p>点击左侧门店查看详情。</p> : null}
          {!detailLoading && detail ? (
            <div className="detail-content">
              <h2>{detail.name}</h2>
              <p>{detail.address || "暂无地址"}</p>
              <p>{detail.transport || "暂无交通信息"}</p>
              <p className="comment">{detail.comment || "暂无备注"}</p>
              <h4>机台列表（{detail.arcades.length}）</h4>
              <ul className="title-list">
                {detail.arcades.map((item, idx) => (
                  <li key={`${item.title_id}-${idx}`}>
                    <b>{item.title_name || "未知机种"}</b>
                    <span>数量: {item.quantity ?? "-"}</span>
                    <span>版本: {item.version || "-"}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </aside>
      </main>
    </div>
  );
}

