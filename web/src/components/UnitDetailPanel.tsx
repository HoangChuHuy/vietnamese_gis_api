import { useState } from "react";
import { getHistory } from "../api/units";
import type { AuditLog, BoundaryFeature } from "../types/api";

interface UnitDetailPanelProps {
  feature: BoundaryFeature | null;
  onViewMergedInto: (code: string) => void;
}

function formatDate(value?: string) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("vi-VN");
}

export default function UnitDetailPanel({ feature, onViewMergedInto }: UnitDetailPanelProps) {
  const [history, setHistory] = useState<AuditLog[] | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);

  if (!feature) {
    return (
      <aside className="detail-panel empty">
        <p>Click vào 1 đơn vị hành chính trên bản đồ để xem chi tiết.</p>
      </aside>
    );
  }

  const p = feature.properties;

  async function handleShowHistory() {
    setLoadingHistory(true);
    try {
      const data = await getHistory(p.unit_code);
      setHistory(data.items);
    } finally {
      setLoadingHistory(false);
    }
  }

  return (
    <aside className="detail-panel">
      <h2>{p.unit_name_with_type ?? p.unit_name}</h2>
      <dl>
        <dt>Mã</dt>
        <dd>{p.unit_code}</dd>
        <dt>Loại</dt>
        <dd>{p.unit_type ?? "—"}</dd>
        <dt>Trạng thái</dt>
        <dd>{p.status === "active" ? "Đang hoạt động" : "Đã ngừng hoạt động"}</dd>
        <dt>Thời kỳ</dt>
        <dd>{p.era === "pre_reform" ? "Trước sáp nhập" : p.era === "post_reform" ? "Sau sáp nhập" : "—"}</dd>
        {p.province_name && (
          <>
            <dt>Tỉnh/Thành phố</dt>
            <dd>{p.province_name}</dd>
          </>
        )}
        {p.district_name && (
          <>
            <dt>Huyện/Quận</dt>
            <dd>{p.district_name}</dd>
          </>
        )}
      </dl>

      {p.merged_into_code && (
        <button className="action-btn" onClick={() => onViewMergedInto(p.merged_into_code!)}>
          Xem đơn vị mới (đã sáp nhập vào {p.merged_into_code})
        </button>
      )}

      <button className="action-btn secondary" onClick={handleShowHistory} disabled={loadingHistory}>
        {loadingHistory ? "Đang tải..." : "Xem lịch sử thay đổi"}
      </button>

      {history && (
        <div className="history-list">
          {history.length === 0 && <p className="hint">Chưa có lịch sử thay đổi.</p>}
          {history.map((log) => (
            <div key={log._id} className="history-item">
              <div className="history-action">{log.action}</div>
              <div className="history-date">{formatDate(log.valid_from)}</div>
              <div className="history-summary">{log.change_summary}</div>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
