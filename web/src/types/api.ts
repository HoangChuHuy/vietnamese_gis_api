export type Era = "pre_reform" | "post_reform";
export type UnitStatus = "active" | "inactive";

export interface AdministrativeUnit {
  _id: string;
  code: string;
  name: string;
  slug?: string;
  type: string;
  node_type?: string;
  name_with_type?: string;
  path?: string;
  path_with_type?: string;
  parent_code?: string;
  parent_id?: string;
  level: number;
  status: UnitStatus;
  era?: Era;
  valid_from?: string;
  valid_to?: string;
  legal_document_id?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  limit: number;
  total: number;
  total_pages: number;
}

export interface BoundaryProperties {
  _id: string;
  unit_id?: string;
  unit_code: string;
  unit_name: string;
  unit_name_with_type?: string;
  unit_type?: string;
  level: number;
  status: UnitStatus;
  province_code?: string;
  province_name?: string;
  district_code?: string;
  district_name?: string;
  parent_code?: string;
  parent_id?: string;
  bbox?: number[];
  srs?: string;
  era?: Era;
  valid_from?: string;
  valid_to?: string;
  source?: string;
  recorded_at?: string;
  merged_into_code?: string;
  geometry_repaired?: boolean;
}

export interface BoundaryFeature {
  type: "Feature";
  geometry: GeoJSON.Geometry;
  properties: BoundaryProperties;
}

export interface BoundaryFeatureCollection {
  type: "FeatureCollection";
  features: BoundaryFeature[];
  page?: number;
  limit?: number;
  total: number;
}

export interface AuditLog {
  _id: string;
  entity_type: string;
  action: string;
  valid_from?: string;
  valid_to?: string;
  system_from?: string;
  system_to?: string;
  created_by?: string;
  legal_document_id?: string;
  before_state?: Record<string, unknown>;
  after_state?: Record<string, unknown>;
  change_summary?: string;
}

export interface LegalDocument {
  _id: string;
  doc_number?: string;
  number?: string;
  serial?: string;
  doc_type?: string;
  issuing_body_code?: string;
  issuing_body?: string;
  issue_date?: string;
  effective_date?: string;
  title?: string;
  scope?: { level?: number; province_code?: string; province_name?: string };
  units_affected?: string[];
  raw_reference?: string;
  created_at?: string;
}

export interface AddressWardOption {
  code: string;
  name: string;
  name_with_type?: string;
}

export type AddressDirection = "old_to_new" | "new_to_old";

export type AddressMatchType = "exact" | "district_candidates" | "split_match" | "not_found";

export interface AddressConvertByNameRequest {
  province_name: string;
  district_name?: string;
  ward_name?: string;
  direction: AddressDirection;
}

/**
 * Đơn vị hành chính trong kết quả /address/convert-by-name — tuỳ nhánh xử lý ở
 * backend mà trả về dạng administrative_units (code/name/name_with_type) hoặc
 * administrative_boundaries (unit_code/unit_name/province_name/district_name),
 * nên gộp chung field của cả 2 dạng, đều optional.
 */
export interface AddressUnitResult {
  code?: string;
  unit_code?: string;
  name?: string;
  unit_name?: string;
  name_with_type?: string;
  unit_name_with_type?: string;
  path_with_type?: string;
  province_name?: string;
  district_name?: string;
  level?: number;
  status?: UnitStatus;
  era?: Era;
  merged_into_code?: string;
  merge_info?: string;
  legal_document?: LegalDocument;
  contribution?: "full" | "partial";
}

export interface AddressConvertByNameResponse {
  input: { province_name: string; district_name?: string; ward_name?: string };
  direction: AddressDirection;
  match_type: AddressMatchType;
  matched_unit: AddressUnitResult | null;
  mapped_units: AddressUnitResult[];
  resolved: boolean;
  note: string;
}
