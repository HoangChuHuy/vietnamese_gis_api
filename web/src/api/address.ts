import { apiGet, apiPost } from "./client";
import type { AddressConvertByNameRequest, AddressConvertByNameResponse, AddressWardOption } from "../types/api";

export function convertAddressByName(payload: AddressConvertByNameRequest): Promise<AddressConvertByNameResponse> {
  return apiPost("/address/convert-by-name", payload);
}

export function listOldDistricts(provinceName: string): Promise<string[]> {
  return apiGet("/address/old-districts", { province_name: provinceName });
}

export function listOldWards(provinceName: string, districtName: string): Promise<AddressWardOption[]> {
  return apiGet("/address/old-wards", { province_name: provinceName, district_name: districtName });
}

export function listNewWards(provinceName: string): Promise<AddressWardOption[]> {
  return apiGet("/address/new-wards", { province_name: provinceName });
}
