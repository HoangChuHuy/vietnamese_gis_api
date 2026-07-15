import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, GeoJSON, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import type { Layer, LeafletMouseEvent } from "leaflet";
import type { Feature } from "geojson";
import type { BoundaryFeature } from "../types/api";

const VIETNAM_CENTER: [number, number] = [16.0, 106.0];
const DEFAULT_ZOOM = 6;

function baseStyle(feature?: Feature) {
  const props = (feature?.properties ?? {}) as BoundaryFeature["properties"];
  const isPreReform = props.era === "pre_reform" || props.status === "inactive";
  return {
    color: isPreReform ? "#f97316" : "#2563eb",
    weight: 1.5,
    dashArray: isPreReform ? "4 3" : undefined,
    fillColor: isPreReform ? "#f97316" : "#2563eb",
    fillOpacity: 0.12,
  };
}

const highlightStyle = {
  color: "#eab308",
  weight: 3,
  fillColor: "#eab308",
  fillOpacity: 0.2,
};

function FitToFeatures({ features }: { features: BoundaryFeature[] }) {
  const map = useMap();
  const signature = features.map((f) => f.properties.unit_code).join(",");
  useEffect(() => {
    if (features.length === 0) return;
    const bounds = L.geoJSON(features as unknown as GeoJSON.GeoJsonObject).getBounds();
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [24, 24] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);
  return null;
}

function FlyToFocus({ feature }: { feature: BoundaryFeature | null | undefined }) {
  const map = useMap();
  useEffect(() => {
    if (!feature) return;
    const bounds = L.geoJSON(feature as unknown as GeoJSON.GeoJsonObject).getBounds();
    if (bounds.isValid()) map.flyToBounds(bounds, { padding: [40, 40], maxZoom: 13 });
  }, [feature, map]);
  return null;
}

function ClickCatcher({
  active,
  onMapClick,
}: {
  active: boolean;
  onMapClick: (lng: number, lat: number) => void;
}) {
  useMapEvents({
    click(e) {
      if (active) onMapClick(e.latlng.lng, e.latlng.lat);
    },
  });
  return null;
}

interface MapViewProps {
  features: BoundaryFeature[];
  focusFeature?: BoundaryFeature | null;
  selectedCode?: string;
  reverseGeocodeMode: boolean;
  onSelectUnit: (code: string) => void;
  onMapClick: (lng: number, lat: number) => void;
}

export default function MapView({
  features,
  focusFeature,
  selectedCode,
  reverseGeocodeMode,
  onSelectUnit,
  onMapClick,
}: MapViewProps) {
  const layerKey = useMemo(
    () => features.map((f) => f.properties.unit_code).join(",") + `|${features.length}`,
    [features]
  );

  const onEachFeature = (feature: Feature, layer: Layer) => {
    if (reverseGeocodeMode) return;
    layer.on("click", (e: LeafletMouseEvent) => {
      L.DomEvent.stopPropagation(e);
      const code = (feature.properties as BoundaryFeature["properties"])?.unit_code;
      if (code) onSelectUnit(code);
    });
  };

  const styleFn = (feature?: Feature) => {
    const code = (feature?.properties as BoundaryFeature["properties"] | undefined)?.unit_code;
    if (code && code === selectedCode) return highlightStyle;
    return baseStyle(feature);
  };

  return (
    <MapContainer
      center={VIETNAM_CENTER}
      zoom={DEFAULT_ZOOM}
      style={{ height: "100%", width: "100%", cursor: reverseGeocodeMode ? "crosshair" : "" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <GeoJSON
        key={layerKey}
        data={{ type: "FeatureCollection", features } as unknown as GeoJSON.GeoJsonObject}
        style={styleFn}
        onEachFeature={onEachFeature}
      />
      {focusFeature && (
        <GeoJSON
          key={`focus-${focusFeature.properties.unit_code}-${focusFeature.properties.era}`}
          data={focusFeature as unknown as GeoJSON.GeoJsonObject}
          style={() => highlightStyle}
        />
      )}
      <FitToFeatures features={features} />
      <FlyToFocus feature={focusFeature} />
      <ClickCatcher active={reverseGeocodeMode} onMapClick={onMapClick} />
    </MapContainer>
  );
}
