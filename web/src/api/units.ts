import { apiGet } from "./client";
import type { AdministrativeUnit, AuditLog, PaginatedResponse } from "../types/api";

export function getUnit(code: string): Promise<AdministrativeUnit> {
  return apiGet(`/units/${encodeURIComponent(code)}`);
}

export async function listProvinces(): Promise<AdministrativeUnit[]> {
  const data = await apiGet<PaginatedResponse<AdministrativeUnit>>("/units", { level: 1, limit: 100 });
  // Vài mã tỉnh có 2 bản ghi trùng code do đổi tên trong đợt sáp nhập (vd Thừa Thiên Huế -> Huế)
  // chưa được dọn dẹp ở nguồn dữ liệu — giữ lại bản ghi xuất hiện sau cùng (mới hơn).
  const byCode = new Map<string, AdministrativeUnit>();
  for (const unit of data.items) byCode.set(unit.code, unit);
  return [...byCode.values()].sort((a, b) =>
    (a.name_with_type ?? a.name).localeCompare(b.name_with_type ?? b.name, "vi")
  );
}

export function searchUnits(q: string, limit = 20): Promise<PaginatedResponse<AdministrativeUnit>> {
  return apiGet(`/units/search`, { q, limit });
}

export function getChildren(code: string): Promise<PaginatedResponse<AdministrativeUnit>> {
  return apiGet(`/units/${encodeURIComponent(code)}/children`, { limit: 200 });
}

export function getHistory(code: string): Promise<PaginatedResponse<AuditLog>> {
  return apiGet(`/units/${encodeURIComponent(code)}/history`, { limit: 50 });
}
