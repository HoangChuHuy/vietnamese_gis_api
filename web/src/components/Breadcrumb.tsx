import type { BoundaryFeature } from "../types/api";

interface BreadcrumbProps {
  feature: BoundaryFeature | null;
  onNavigateCountry: () => void;
  onNavigateProvince: (provinceCode: string) => void;
  onNavigateDistrict: (districtCode: string | undefined) => void;
}

export default function Breadcrumb({
  feature,
  onNavigateCountry,
  onNavigateProvince,
  onNavigateDistrict,
}: BreadcrumbProps) {
  const p = feature?.properties;

  return (
    <div className="breadcrumb">
      <span className="crumb link" onClick={onNavigateCountry}>
        Toàn quốc
      </span>
      {p?.province_name && (
        <>
          {" / "}
          <span className="crumb link" onClick={() => p.province_code && onNavigateProvince(p.province_code)}>
            {p.province_name}
          </span>
        </>
      )}
      {p?.district_name && (
        <>
          {" / "}
          <span className="crumb link" onClick={() => onNavigateDistrict(p.district_code)}>
            {p.district_name}
          </span>
        </>
      )}
      {p && (
        <>
          {" / "}
          <span className="crumb current">{p.unit_name_with_type ?? p.unit_name}</span>
        </>
      )}
    </div>
  );
}
