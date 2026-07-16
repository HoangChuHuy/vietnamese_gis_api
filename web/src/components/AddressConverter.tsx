import { useEffect, useState } from "react";
import { convertAddressByName, listNewWards, listOldDistricts, listOldWards } from "../api/address";
import { ApiError } from "../api/client";
import { listProvinces } from "../api/units";
import type {
  AddressConvertByNameResponse,
  AddressDirection,
  AddressUnitResult,
  AddressWardOption,
  AdministrativeUnit,
  Era,
} from "../types/api";

interface AddressConverterProps {
  onClose: () => void;
  onFocusUnit: (code: string, era: Era) => void;
}

function unitCode(u: AddressUnitResult): string {
  return u.unit_code ?? u.code ?? "—";
}

function unitDisplayName(u: AddressUnitResult): string {
  return u.unit_name_with_type ?? u.name_with_type ?? u.unit_name ?? u.name ?? "—";
}

function unitEra(u: AddressUnitResult): Era {
  return u.era ?? "post_reform";
}

function formatDate(value?: string) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("vi-VN");
}

function LegalDocumentCard({ unit }: { unit: AddressUnitResult }) {
  const ld = unit.legal_document;
  if (!ld) return null;
  return (
    <div className="legal-doc-card">
      <div className="legal-doc-title">{ld.doc_number ?? "Văn bản pháp lý"}</div>
      {ld.title && <div className="legal-doc-name">{ld.title}</div>}
      <dl>
        <dt>Cơ quan ban hành</dt>
        <dd>{ld.issuing_body ?? "—"}</dd>
        <dt>Ngày ban hành</dt>
        <dd>{formatDate(ld.issue_date)}</dd>
        <dt>Ngày hiệu lực</dt>
        <dd>{formatDate(ld.effective_date)}</dd>
      </dl>
    </div>
  );
}

function UnitResultCard({
  unit,
  onFocusUnit,
}: {
  unit: AddressUnitResult;
  onFocusUnit: (code: string, era: Era) => void;
}) {
  return (
    <div className="address-unit-card">
      <div className="address-unit-head">
        <span className="address-unit-name">{unitDisplayName(unit)}</span>
        <span className="code">{unitCode(unit)}</span>
      </div>
      {unit.contribution === "partial" && <span className="badge partial">chỉ góp một phần</span>}
      {(unit.province_name || unit.district_name) && (
        <div className="address-unit-path">
          {[unit.district_name, unit.province_name].filter(Boolean).join(", ")}
        </div>
      )}
      {unit.merge_info && <div className="address-unit-merge-info">Sáp nhập từ: {unit.merge_info}</div>}
      <button className="action-btn secondary small" onClick={() => onFocusUnit(unitCode(unit), unitEra(unit))}>
        Xem trên bản đồ
      </button>
      <LegalDocumentCard unit={unit} />
    </div>
  );
}

export default function AddressConverter({ onClose, onFocusUnit }: AddressConverterProps) {
  const [direction, setDirection] = useState<AddressDirection>("old_to_new");

  const [provinces, setProvinces] = useState<AdministrativeUnit[]>([]);
  const [provinceName, setProvinceName] = useState("");

  const [districtOptions, setDistrictOptions] = useState<string[]>([]);
  const [districtName, setDistrictName] = useState("");
  const [loadingDistricts, setLoadingDistricts] = useState(false);

  const [wardOptions, setWardOptions] = useState<AddressWardOption[]>([]);
  const [wardName, setWardName] = useState("");
  const [loadingWards, setLoadingWards] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<AddressUnitResult[] | null>(null);
  const [result, setResult] = useState<AddressConvertByNameResponse | null>(null);

  useEffect(() => {
    listProvinces().then(setProvinces);
  }, []);

  // Đổi tỉnh hoặc đổi chiều tra cứu -> nạp lại bước tiếp theo, xoá lựa chọn cũ.
  useEffect(() => {
    setDistrictName("");
    setDistrictOptions([]);
    setWardName("");
    setWardOptions([]);
    setResult(null);
    setCandidates(null);
    setError(null);

    if (!provinceName) return;

    if (direction === "old_to_new") {
      setLoadingDistricts(true);
      listOldDistricts(provinceName)
        .then(setDistrictOptions)
        .finally(() => setLoadingDistricts(false));
    } else {
      setLoadingWards(true);
      listNewWards(provinceName)
        .then(setWardOptions)
        .finally(() => setLoadingWards(false));
    }
  }, [provinceName, direction]);

  // Đổi quận/huyện (chỉ áp dụng chiều cũ -> mới) -> nạp danh sách xã/phường cũ.
  useEffect(() => {
    setWardName("");
    setWardOptions([]);
    setResult(null);
    setCandidates(null);

    if (direction !== "old_to_new" || !provinceName || !districtName) return;

    setLoadingWards(true);
    listOldWards(provinceName, districtName)
      .then(setWardOptions)
      .finally(() => setLoadingWards(false));
  }, [districtName, provinceName, direction]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setCandidates(null);
    setResult(null);
    try {
      const data = await convertAddressByName({
        province_name: provinceName,
        district_name: districtName || undefined,
        ward_name: wardName || undefined,
        direction,
      });
      setResult(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
        const detail = err.detail as { candidates?: AddressUnitResult[] } | null;
        if (detail && Array.isArray(detail.candidates)) setCandidates(detail.candidates);
      } else {
        setError(err instanceof Error ? err.message : "Đã có lỗi xảy ra.");
      }
    } finally {
      setLoading(false);
    }
  }

  const canSubmit = provinceName && (direction === "new_to_old" || !wardName || districtName);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal address-converter" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Tra cứu địa chỉ cũ ↔ mới sau sáp nhập</h2>
          <button className="modal-close" onClick={onClose} aria-label="Đóng">
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Chiều tra cứu</label>
            <select value={direction} onChange={(e) => setDirection(e.target.value as AddressDirection)}>
              <option value="old_to_new">Địa chỉ cũ → địa chỉ mới</option>
              <option value="new_to_old">Địa chỉ mới → (các) địa chỉ cũ</option>
            </select>
          </div>

          <div className="field">
            <label>Tỉnh / Thành phố *</label>
            <select value={provinceName} onChange={(e) => setProvinceName(e.target.value)} required>
              <option value="">-- Chọn tỉnh/thành --</option>
              {provinces.map((p) => {
                const value = p.name_with_type ?? p.name;
                return (
                  <option key={p.code} value={value}>
                    {value}
                  </option>
                );
              })}
            </select>
          </div>

          {direction === "old_to_new" && (
            <div className="field">
              <label>Quận / Huyện cũ {wardName && "*"}</label>
              <select
                value={districtName}
                onChange={(e) => setDistrictName(e.target.value)}
                disabled={!provinceName || loadingDistricts}
              >
                <option value="">
                  {loadingDistricts ? "Đang tải..." : "-- Chọn quận/huyện --"}
                </option>
                {districtOptions.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
              <div className="hint">Bắt buộc nếu chọn xã/phường cũ — dùng để tra chính xác và làm fallback.</div>
            </div>
          )}

          <div className="field">
            <label>Xã / Phường {direction === "old_to_new" ? "cũ" : "mới"}</label>
            <select
              value={wardName}
              onChange={(e) => setWardName(e.target.value)}
              disabled={
                loadingWards || (direction === "old_to_new" ? !districtName : !provinceName)
              }
            >
              <option value="">{loadingWards ? "Đang tải..." : "-- Chọn xã/phường (không bắt buộc) --"}</option>
              {wardOptions.map((w) => (
                <option key={w.code} value={w.name}>
                  {w.name_with_type ?? w.name}
                </option>
              ))}
            </select>
          </div>

          <button className="action-btn" type="submit" disabled={loading || !canSubmit}>
            {loading ? "Đang tra cứu..." : "Tra cứu"}
          </button>
        </form>

        {error && <div className="notfound-banner static">{error}</div>}

        {candidates && candidates.length > 0 && (
          <div className="address-results">
            <div className="hint">Có nhiều đơn vị trùng tên, vui lòng chọn / nhập chính xác hơn:</div>
            {candidates.map((c, i) => (
              <UnitResultCard key={i} unit={c} onFocusUnit={onFocusUnit} />
            ))}
          </div>
        )}

        {result && (
          <div className="address-results">
            <div className={`address-note ${result.resolved ? "" : "warn"}`}>{result.note}</div>

            {result.matched_unit && (
              <>
                <div className="hint">Đơn vị khớp với dữ liệu nhập:</div>
                <UnitResultCard unit={result.matched_unit} onFocusUnit={onFocusUnit} />
              </>
            )}

            {result.mapped_units.length > 0 && (
              <>
                <div className="hint">
                  {result.match_type === "district_candidates"
                    ? `Danh sách ${result.mapped_units.length} đơn vị mới có thể tương ứng:`
                    : result.match_type === "split_match"
                      ? `Xã/phường cũ đã bị tách vào ${result.mapped_units.length} đơn vị mới:`
                      : "Kết quả mapping:"}
                </div>
                {result.mapped_units.map((u, i) => (
                  <UnitResultCard key={i} unit={u} onFocusUnit={onFocusUnit} />
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
