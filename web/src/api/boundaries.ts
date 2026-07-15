import { apiGet } from "./client";
import type { BoundaryFeature, BoundaryFeatureCollection, Era } from "../types/api";

const PAGE_LIMIT = 200;
const MAX_FEATURES = 2000;

export interface ListBoundariesParams {
  provinceCode?: string;
  level?: number;
  era?: Era;
  status?: string;
}

export async function listBoundaries(params: ListBoundariesParams): Promise<BoundaryFeature[]> {
  const features: BoundaryFeature[] = [];
  let page = 1;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const data: BoundaryFeatureCollection = await apiGet("/boundaries", {
      province_code: params.provinceCode,
      level: params.level,
      era: params.era,
      status: params.status,
      page,
      limit: PAGE_LIMIT,
    });
    features.push(...data.features);
    const gotAll = features.length >= data.total || data.features.length < PAGE_LIMIT;
    if (gotAll || features.length >= MAX_FEATURES) break;
    page += 1;
  }
  return features;
}

export function getBoundary(unitCode: string, era?: Era): Promise<BoundaryFeature | null> {
  return apiGet(`/boundaries/${encodeURIComponent(unitCode)}`, { era });
}
