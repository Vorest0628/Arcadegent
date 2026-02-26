import { FormEvent, useEffect, useMemo, useState } from "react";
import { getArcadeDetail, listArcades, listCities, listCounties, listProvinces } from "../api/client";
import type { ArcadeDetail, ArcadeSummary, PagedArcades, RegionItem } from "../types";

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

export function ArcadeBrowser() {
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
      setError(err instanceof Error ? err.message : "Search failed");
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
      return "No results";
    }
    const start = (paged.page - 1) * paged.page_size + 1;
    const end = Math.min(paged.total, paged.page * paged.page_size);
    return `${start}-${end} / ${paged.total}`;
  }, [paged]);

  return (
    <div className="browser-shell">
      <header className="browser-hero">
        <h2>Arcade Explorer</h2>
        <p>Filter shops by keyword and region, then inspect title machine details.</p>
      </header>

      <main className="browser-layout">
        <section className="browser-card browser-controls">
          <form onSubmit={onSubmit} className="browser-filter-grid">
            <label className="browser-field">
              Keyword
              <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="maimai / chunithm" />
            </label>
            <label className="browser-field">
              Province
              <select value={provinceCode} onChange={(e) => setProvinceCode(e.target.value)}>
                <option value="">All</option>
                {provinces.map((row) => (
                  <option value={row.code} key={row.code}>
                    {row.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="browser-field">
              City
              <select value={cityCode} onChange={(e) => setCityCode(e.target.value)} disabled={!provinceCode}>
                <option value="">All</option>
                {cities.map((row) => (
                  <option value={row.code} key={row.code}>
                    {row.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="browser-field">
              County
              <select value={countyCode} onChange={(e) => setCountyCode(e.target.value)} disabled={!cityCode}>
                <option value="">All</option>
                {counties.map((row) => (
                  <option value={row.code} key={row.code}>
                    {row.name}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" disabled={loading} className="browser-primary-btn">
              {loading ? "Searching..." : "Search"}
            </button>
          </form>

          {error ? <div className="browser-error">{error}</div> : null}

          <div className="browser-list-header">
            <strong>Results</strong>
            <span>{pageHint}</span>
          </div>

          <ul className="browser-result-list">
            {paged.items.map((item) => (
              <li key={item.source_id}>
                <button type="button" onClick={() => openDetail(item)} className="browser-item-btn">
                  <h3>{item.name}</h3>
                  <p>{item.address || "No address"}</p>
                  <small>
                    {item.province_name || "-"} / {item.city_name || "-"} / {item.county_name || "-"} | titles {" "}
                    {item.arcade_count}
                  </small>
                </button>
              </li>
            ))}
          </ul>

          <div className="browser-pager">
            <button
              type="button"
              disabled={paged.page <= 1 || loading}
              onClick={() => void runSearch(Math.max(1, paged.page - 1))}
              className="browser-secondary-btn"
            >
              Prev
            </button>
            <span>
              Page {paged.page} / {Math.max(1, paged.total_pages)}
            </span>
            <button
              type="button"
              disabled={paged.page >= paged.total_pages || loading || paged.total_pages === 0}
              onClick={() => void runSearch(paged.page + 1)}
              className="browser-secondary-btn"
            >
              Next
            </button>
          </div>
        </section>

        <aside className="browser-card browser-detail">
          <div className="browser-detail-head">
            <strong>Shop Detail</strong>
          </div>
          {detailLoading ? <p>Loading detail...</p> : null}
          {!detailLoading && !detail ? <p>Select one shop from the left list.</p> : null}
          {!detailLoading && detail ? (
            <div className="browser-detail-content">
              <h3>{detail.name}</h3>
              <p>{detail.address || "No address"}</p>
              <p>{detail.transport || "No transport info"}</p>
              <p className="browser-comment">{detail.comment || "No comments"}</p>
              <h4>Titles ({detail.arcades.length})</h4>
              <ul className="browser-title-list">
                {detail.arcades.map((item, idx) => (
                  <li key={`${item.title_id}-${idx}`}>
                    <b>{item.title_name || "Unknown"}</b>
                    <span>Qty: {item.quantity ?? "-"}</span>
                    <span>Version: {item.version || "-"}</span>
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
