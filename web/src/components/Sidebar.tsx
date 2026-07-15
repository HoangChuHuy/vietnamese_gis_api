import { useEffect, useState } from "react";
import { listProvinces, searchUnits } from "../api/units";
import type { AdministrativeUnit, Era } from "../types/api";

interface SidebarProps {
  era: Era | undefined;
  onEraChange: (era: Era | undefined) => void;
  provinceCode: string | undefined;
  onProvinceChange: (code: string | undefined) => void;
  districts: [string, string][];
  districtFilter: string | undefined;
  onDistrictFilterChange: (code: string | undefined) => void;
  reverseGeocodeMode: boolean;
  onReverseGeocodeModeChange: (active: boolean) => void;
  onSelectSearchResult: (unit: AdministrativeUnit) => void;
  onReset: () => void;
}

export default function Sidebar({
  era,
  onEraChange,
  provinceCode,
  onProvinceChange,
  districts,
  districtFilter,
  onDistrictFilterChange,
  reverseGeocodeMode,
  onReverseGeocodeModeChange,
  onSelectSearchResult,
  onReset,
}: SidebarProps) {
  const [provinces, setProvinces] = useState<AdministrativeUnit[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<AdministrativeUnit[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    listProvinces().then(setProvinces);
  }, []);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const data = await searchUnits(query.trim());
        setResults(data.items);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  return (
    <aside className="sidebar">
      <h1>Bản đồ hành chính Việt Nam</h1>

      <button className="reset-btn" onClick={onReset}>
        Về toàn quốc
      </button>

      <div className="field">
        <label>Tìm kiếm đơn vị hành chính</label>
        <input
          type="text"
          placeholder="Nhập tên xã/huyện/tỉnh..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {searching && <div className="hint">Đang tìm...</div>}
        {results.length > 0 && (
          <ul className="search-results">
            {results.map((unit) => (
              <li
                key={unit._id}
                onClick={() => {
                  onSelectSearchResult(unit);
                  setQuery("");
                  setResults([]);
                }}
              >
                {unit.name_with_type ?? unit.name}
                <span className="code">{unit.code}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="field">
        <label>Tỉnh / Thành phố</label>
        <select value={provinceCode ?? ""} onChange={(e) => onProvinceChange(e.target.value || undefined)}>
          <option value="">-- Chọn tỉnh/thành --</option>
          {provinces.map((p) => (
            <option key={p.code} value={p.code}>
              {p.name_with_type ?? p.name}
            </option>
          ))}
        </select>
      </div>

      {districts.length > 0 && (
        <div className="field">
          <label>Huyện/Quận (trước sáp nhập)</label>
          <select
            value={districtFilter ?? ""}
            onChange={(e) => onDistrictFilterChange(e.target.value || undefined)}
          >
            <option value="">-- Tất cả --</option>
            {districts.map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="field">
        <label>Thời điểm địa giới</label>
        <select
          value={era ?? ""}
          onChange={(e) => onEraChange((e.target.value || undefined) as Era | undefined)}
        >
          <option value="">Tất cả (so sánh trước/sau)</option>
          <option value="post_reform">Sau sáp nhập (07/2025)</option>
          <option value="pre_reform">Trước sáp nhập</option>
        </select>
      </div>

      <div className="field">
        <label>
          <input
            type="checkbox"
            checked={reverseGeocodeMode}
            onChange={(e) => onReverseGeocodeModeChange(e.target.checked)}
          />
          {" "}Tra cứu toạ độ (click vào bản đồ)
        </label>
      </div>
    </aside>
  );
}
