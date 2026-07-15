import { useCallback, useEffect, useMemo, useState } from "react";
import MapView from "./components/MapView";
import Sidebar from "./components/Sidebar";
import Breadcrumb from "./components/Breadcrumb";
import Legend from "./components/Legend";
import UnitDetailPanel from "./components/UnitDetailPanel";
import { useProvinceWards } from "./hooks/useBoundaries";
import { getBoundary } from "./api/boundaries";
import { reverseGeocode } from "./api/geocode";
import type { AdministrativeUnit, BoundaryFeature, Era } from "./types/api";

export default function App() {
  const [era, setEra] = useState<Era | undefined>("post_reform");
  const [provinceCode, setProvinceCode] = useState<string | undefined>();
  const [districtFilter, setDistrictFilter] = useState<string | undefined>();
  const [selectedFeature, setSelectedFeature] = useState<BoundaryFeature | null>(null);
  const [focusFeature, setFocusFeature] = useState<BoundaryFeature | null>(null);
  const [reverseGeocodeMode, setReverseGeocodeMode] = useState(false);
  const [notFoundMsg, setNotFoundMsg] = useState<string | null>(null);

  const { features, loading } = useProvinceWards(provinceCode, era);

  const districts = useMemo(() => {
    const map = new Map<string, string>();
    for (const f of features) {
      const { district_code, district_name } = f.properties;
      if (district_code && district_name) map.set(district_code, district_name);
    }
    return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1], "vi"));
  }, [features]);

  const displayedFeatures = useMemo(
    () => (districtFilter ? features.filter((f) => f.properties.district_code === districtFilter) : features),
    [features, districtFilter]
  );

  // Nếu feature đang focus (từ search/reverse-geocode/merged_into) đã nằm trong layer chính
  // đang hiển thị thì bỏ layer overlay riêng để tránh vẽ trùng.
  useEffect(() => {
    if (
      focusFeature &&
      displayedFeatures.some((f) => f.properties.unit_code === focusFeature.properties.unit_code)
    ) {
      setFocusFeature(null);
    }
  }, [displayedFeatures, focusFeature]);

  const focusOnFeature = useCallback((feature: BoundaryFeature) => {
    setSelectedFeature(feature);
    setFocusFeature(feature);
    setProvinceCode(feature.properties.province_code);
    setDistrictFilter(feature.properties.district_code);
    if (feature.properties.era) setEra(feature.properties.era);
  }, []);

  const handleSelectUnit = useCallback(
    (code: string) => {
      const feature = features.find((f) => f.properties.unit_code === code);
      if (feature) {
        setSelectedFeature(feature);
        setFocusFeature(null);
      }
    },
    [features]
  );

  const handleSelectProvince = useCallback((code: string | undefined) => {
    setProvinceCode(code);
    setDistrictFilter(undefined);
    setSelectedFeature(null);
    setFocusFeature(null);
    setNotFoundMsg(null);
  }, []);

  const handleSelectSearchResult = useCallback(
    async (unit: AdministrativeUnit) => {
      setNotFoundMsg(null);
      if (unit.level === 1) {
        handleSelectProvince(unit.code);
        return;
      }
      const feature = await getBoundary(unit.code, era);
      if (feature) {
        focusOnFeature(feature);
        return;
      }
      if (unit.level === 2 && unit.parent_code) {
        // Đơn vị cấp huyện (đã bỏ sau sáp nhập) không có polygon riêng — chuyển sang xem
        // danh sách xã của huyện đó (lọc theo district_code = mã huyện).
        setProvinceCode(unit.parent_code);
        setDistrictFilter(unit.code);
        setSelectedFeature(null);
        setFocusFeature(null);
      } else {
        setNotFoundMsg(`Không có dữ liệu ranh giới cho ${unit.name_with_type ?? unit.name}`);
      }
    },
    [era, focusOnFeature, handleSelectProvince]
  );

  const handleViewMergedInto = useCallback(
    async (code: string) => {
      setNotFoundMsg(null);
      const feature = await getBoundary(code, "post_reform");
      if (feature) focusOnFeature(feature);
      else setNotFoundMsg(`Không tìm thấy ranh giới cho đơn vị ${code}`);
    },
    [focusOnFeature]
  );

  const handleMapClick = useCallback(
    async (lng: number, lat: number) => {
      setNotFoundMsg(null);
      const feature = await reverseGeocode(lng, lat);
      if (feature) focusOnFeature(feature);
      else setNotFoundMsg("Không tìm thấy đơn vị hành chính chứa toạ độ này.");
    },
    [focusOnFeature]
  );

  const handleReset = useCallback(() => handleSelectProvince(undefined), [handleSelectProvince]);

  return (
    <div className="app-layout">
      <Sidebar
        era={era}
        onEraChange={setEra}
        provinceCode={provinceCode}
        onProvinceChange={handleSelectProvince}
        districts={districts}
        districtFilter={districtFilter}
        onDistrictFilterChange={setDistrictFilter}
        reverseGeocodeMode={reverseGeocodeMode}
        onReverseGeocodeModeChange={setReverseGeocodeMode}
        onSelectSearchResult={handleSelectSearchResult}
        onReset={handleReset}
      />
      <main className="map-area">
        <Breadcrumb
          feature={selectedFeature}
          onNavigateCountry={handleReset}
          onNavigateProvince={(code) => handleSelectProvince(code)}
          onNavigateDistrict={setDistrictFilter}
        />
        {loading && <div className="loading-banner">Đang tải ranh giới...</div>}
        {notFoundMsg && <div className="notfound-banner">{notFoundMsg}</div>}
        {!provinceCode && !loading && (
          <div className="notfound-banner hint-banner">
            Chọn 1 tỉnh/thành ở bên trái (hoặc tìm kiếm 1 xã/phường) để xem ranh giới.
          </div>
        )}
        <MapView
          features={displayedFeatures}
          focusFeature={focusFeature}
          selectedCode={selectedFeature?.properties.unit_code}
          reverseGeocodeMode={reverseGeocodeMode}
          onSelectUnit={handleSelectUnit}
          onMapClick={handleMapClick}
        />
        <Legend />
      </main>
      <UnitDetailPanel feature={selectedFeature} onViewMergedInto={handleViewMergedInto} />
    </div>
  );
}
