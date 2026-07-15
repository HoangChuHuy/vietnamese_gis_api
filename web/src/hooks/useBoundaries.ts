import { useEffect, useState } from "react";
import { listBoundaries } from "../api/boundaries";
import type { BoundaryFeature, Era } from "../types/api";

/**
 * Collection administrative_boundaries chỉ lưu polygon cấp xã/phường (không có polygon
 * tỉnh/huyện) — field `level` không phản ánh nhất quán tỉnh/huyện/xã trên dữ liệu thực tế,
 * nên cách tin cậy để lấy toàn bộ xã của 1 tỉnh là lọc theo province_code + era, không dùng level.
 * Lọc theo huyện (chỉ có ở dữ liệu pre_reform, qua district_code) thực hiện phía client.
 */
export function useProvinceWards(provinceCode: string | undefined, era?: Era) {
  const [features, setFeatures] = useState<BoundaryFeature[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!provinceCode) {
      setFeatures([]);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const result = await listBoundaries({ provinceCode, era });
        if (!cancelled) setFeatures(result);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [provinceCode, era]);

  return { features, loading };
}
