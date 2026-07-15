import { apiGet } from "./client";
import type { BoundaryFeature } from "../types/api";

export function reverseGeocode(lng: number, lat: number): Promise<BoundaryFeature | null> {
  return apiGet("/geocode/reverse", { lng, lat });
}
