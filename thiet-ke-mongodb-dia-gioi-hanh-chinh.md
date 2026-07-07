# Thiết kế MongoDB — Quản lý địa giới hành chính Việt Nam (Temporal + Geospatial)

> Tài liệu kỹ thuật thiết kế cơ sở dữ liệu MongoDB theo mô hình **bi-temporal** (versioning theo thời gian) kết hợp **geospatial** (GeoJSON + 2dsphere), phục vụ quản lý địa giới hành chính trước/sau sáp nhập, chuyển đổi địa chỉ, bản đồ ranh giới và bản đồ quy hoạch dài hạn.

---

## 0. Nguyên tắc thiết kế cốt lõi

Trước khi đi vào collection, cần thống nhất các nguyên tắc nền tảng — đây là phần quyết định việc hệ thống có "sống" được qua các đợt cải cách hành chính hay không (ví dụ thực tế: chuyển mô hình 3 cấp → 2 cấp, bỏ cấp huyện, sáp nhập tỉnh).

1. **Tách "thực thể ổn định" khỏi "phiên bản theo thời gian".** Một đơn vị hành chính (Administrative Unit) có một `_id` nội bộ **bất biến suốt vòng đời**. Mọi thuộc tính có thể thay đổi (tên, cấp, đơn vị cha, mã GSO) đều nằm ở `administrative_unit_versions` với khoảng hiệu lực `[valid_from, valid_to)`.

2. **Không hard-code cấp hành chính.** `level` là thuộc tính của *version*, không phải của entity. Một đơn vị có thể đổi cấp (ví dụ huyện → thành phố thuộc tỉnh; hoặc bị xóa cấp). Hệ thống không được giả định "luôn 3 cấp tỉnh/huyện/xã".

3. **Không mất lịch sử.** Khi sáp nhập/đổi tên, KHÔNG update đè (in-place) phiên bản cũ. Ta **đóng** version cũ (set `valid_to`) và **mở** version mới. Đơn vị cũ vẫn truy vấn được tại thời điểm trong quá khứ.

4. **Mô hình half-open interval `[valid_from, valid_to)`.** `valid_to = null` nghĩa là "còn hiệu lực đến hiện tại". Quy ước nửa mở giúp tránh trùng lặp tại điểm giao (một ngày chỉ thuộc đúng một version).

5. **Bi-temporal (khuyến nghị production).** Phân biệt:
   - **Valid time** (`valid_from`/`valid_to`): thời điểm thay đổi *có hiệu lực trong thực tế* (theo ngày hiệu lực của văn bản pháp lý).
   - **Transaction time** (`recorded_at` + `audit_logs`): thời điểm dữ liệu *được ghi nhận vào DB*. Dùng để trả lời "ngày X, hệ thống tin rằng địa giới là gì" — quan trọng khi văn bản pháp lý ban hành trễ hoặc bị đính chính.

6. **Tham chiếu cha theo entity, không theo version.** `parent_unit_id` trỏ tới `administrative_units._id` (ổn định), KHÔNG trỏ tới version cụ thể. Lý do: khi cha đổi tên, con không cần re-version theo. Quan hệ cha-con được "giải" (resolve) tại thời điểm truy vấn theo ngày.

---

## 1. Danh sách collections

| # | Collection | Vai trò | Loại dữ liệu |
|---|------------|---------|--------------|
| 1 | `administrative_units` | Thực thể hành chính ổn định (danh tính bất biến) | Master |
| 2 | `administrative_unit_versions` | Phiên bản theo thời gian: tên, cấp, cha, mã | Temporal |
| 3 | `administrative_boundaries` | Ranh giới địa lý GeoJSON theo thời gian | Geospatial + Temporal |
| 4 | `merger_mappings` | Sự kiện tái cơ cấu: cũ → mới (merge/split/...) | Event graph |
| 5 | `address_conversion_rules` | Luật chuyển đổi địa chỉ cũ → mới | Mapping |
| 6 | `legal_documents` | Văn bản pháp lý / quyết định hành chính | Reference |
| 7 | `map_layers` | Danh mục/định nghĩa lớp bản đồ (kèm style, nguồn tile) | Catalog |
| 8 | `planning_maps` | Đồ án/bộ quy hoạch (kỳ quy hoạch, tầm nhìn) | Master |
| 9 | `planning_zones` | Vùng quy hoạch cụ thể (polygon) trong một đồ án | Geospatial |
| 10 | `geospatial_files` | File gốc shapefile/geojson/kml/geotiff (metadata + storage) | Asset |
| 11 | `audit_logs` | Nhật ký thay đổi (transaction time, diff) | Audit |

---

## 2. Mục đích từng collection

- **administrative_units** — "sổ hộ khẩu" của các thực thể. Mỗi đơn vị có một ID nội bộ duy nhất, không bao giờ đổi, kể cả khi đơn vị bị sáp nhập/giải thể. Đây là điểm neo để mọi version, boundary, merger gắn vào.
- **administrative_unit_versions** — lịch sử "khai sinh – khai tử" thuộc tính. Trả lời: *"Tại ngày D, đơn vị U tên là gì, cấp gì, thuộc cha nào?"*
- **administrative_boundaries** — hình học ranh giới (Polygon/MultiPolygon) tách riêng để tối ưu dung lượng và geospatial query. Một đơn vị có thể đổi ranh giới mà không đổi tên, hoặc ngược lại.
- **merger_mappings** — mô hình hóa *sự kiện* sáp nhập/chia tách như một cạnh đồ thị nhiều-nhiều giữa tập đơn vị nguồn và tập đơn vị đích. Đây là "sự thật pháp lý" của việc tái cơ cấu.
- **address_conversion_rules** — luật chuyển đổi địa chỉ ở mọi cấp (tỉnh/huyện/xã), phục vụ tra cứu nhanh "địa chỉ cũ → địa chỉ mới" mà không phải suy luận từ merger graph mỗi lần.
- **legal_documents** — nguồn pháp lý gốc (Nghị quyết Quốc hội/UBTVQH, Nghị định, Quyết định). Mọi thay đổi đều phải dẫn chiếu về đây.
- **map_layers** — danh mục lớp (giao thông, đô thị, KCN, dân cư, hành chính, bảo tồn, hạ tầng…), kèm style hiển thị và cấu hình nguồn (internal / Mapbox / Google / OSM).
- **planning_maps** — một bộ quy hoạch hoàn chỉnh, có phạm vi, kỳ quy hoạch và tầm nhìn (ví dụ tầm nhìn 100 năm), trạng thái phê duyệt.
- **planning_zones** — từng vùng quy hoạch (polygon) thuộc một `planning_map` và một `map_layer`, mang thuộc tính quy hoạch (loại đất, mật độ, tầng cao…).
- **geospatial_files** — quản lý file dữ liệu gốc lớn (shapefile, GeoTIFF…), lưu metadata trong Mongo, nội dung file ở GridFS hoặc object storage (S3/MinIO).
- **audit_logs** — ghi nhận ai, lúc nào, đổi gì (before/after), theo văn bản nào — đáp ứng yêu cầu kiểm toán và truy vết bi-temporal.

---

## 3. & 4. Schema chi tiết + ý nghĩa từng field

### 3.1 `administrative_units`

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|-------|------|:---:|---------|
| `_id` | ObjectId | ✓ | ID nội bộ bất biến (danh tính ổn định) |
| `unit_code` | string | ✓ | Mã định danh ổn định nội bộ (vd `VN-AU-0000123`). KHÔNG dùng mã GSO làm khóa chính vì mã GSO có thể tái sử dụng/đổi |
| `country` | string | ✓ | Mã quốc gia ISO (`VN`) — dự phòng đa quốc gia |
| `nominal_kind` | string | | Loại "khái niệm" ổn định (`territory`) — KHÔNG chứa cấp cụ thể vì cấp thuộc version |
| `status` | enum | ✓ | `active` / `dissolved` (đã giải thể) |
| `current_version_id` | ObjectId | | Con trỏ denormalized tới version đang hiệu lực (tăng tốc đọc "hiện tại") |
| `current_parent_id` | ObjectId | | Denormalized cha hiện tại (tùy chọn, để dựng cây nhanh) |
| `created_at` / `updated_at` | date | ✓ | Dấu thời gian transaction |

### 3.2 `administrative_unit_versions`

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|-------|------|:---:|---------|
| `_id` | ObjectId | ✓ | Khóa version |
| `unit_id` | ObjectId → units | ✓ | Trỏ về thực thể ổn định |
| `version_no` | int | ✓ | Số thứ tự version của đơn vị (1,2,3…) |
| `name` | string | ✓ | Tên gọi tại version (vd `Hà Nội`) |
| `full_name` | string | ✓ | Tên đầy đủ kèm loại (vd `Thành phố Hà Nội`) |
| `name_en` | string | | Tên tiếng Anh (tích hợp bản đồ quốc tế) |
| `name_normalized` | string | ✓ | Tên đã chuẩn hóa không dấu, lowercase (phục vụ search/khớp địa chỉ) |
| `level` | enum | ✓ | Cấp hành chính: `province` / `district` / `ward`. **Có thể đổi giữa các version** |
| `unit_type` | enum | ✓ | Loại chi tiết: `tinh`, `thanh_pho_tw`, `huyen`, `quan`, `thi_xa`, `thanh_pho_thuoc_tinh`, `phuong`, `xa`, `thi_tran` |
| `parent_unit_id` | ObjectId → units | | Cha (theo entity, null nếu là cấp cao nhất) |
| `official_codes` | object | | Mã chính thống tại thời điểm đó: `{ gso: "01", postal: "100000" }` |
| `valid_from` | date | ✓ | Ngày bắt đầu hiệu lực (= ngày hiệu lực văn bản) |
| `valid_to` | date \| null | ✓ | Ngày kết thúc (null = còn hiệu lực). Nửa mở `[from, to)` |
| `change_type` | enum | ✓ | `established` / `renamed` / `reparented` / `level_changed` / `merged_into` / `split_into` / `boundary_changed` / `dissolved` |
| `legal_document_ids` | [ObjectId] | | Văn bản căn cứ cho version này |
| `boundary_id` | ObjectId → boundaries | | Ranh giới tương ứng (tùy chọn; xem mục trade-off) |
| `merger_mapping_id` | ObjectId | | Sự kiện tái cơ cấu sinh ra version này |
| `recorded_at` | date | ✓ | Transaction time — khi ghi vào DB |
| `status` | enum | ✓ | `active` / `superseded` |

### 3.3 `administrative_boundaries`

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|-------|------|:---:|---------|
| `_id` | ObjectId | ✓ | Khóa boundary |
| `unit_id` | ObjectId → units | ✓ | Đơn vị sở hữu ranh giới |
| `version_id` | ObjectId → versions | | Gắn với version cụ thể (tùy chọn) |
| `geometry` | GeoJSON | ✓ | `Polygon` hoặc `MultiPolygon`, tọa độ `[lng, lat]`, hệ WGS84 |
| `centroid` | GeoJSON Point | | Tâm để đặt nhãn / zoom |
| `bbox` | [number] | | Bounding box `[minLng,minLat,maxLng,maxLat]` |
| `area_km2` | double | | Diện tích tính sẵn |
| `valid_from` / `valid_to` | date | ✓ | Khoảng hiệu lực của ranh giới (độc lập với version tên) |
| `srs` | string | ✓ | Hệ quy chiếu, mặc định `EPSG:4326` |
| `simplified` | object | | Hình học rút gọn theo zoom: `{ z6: GeoJSON, z10: GeoJSON }` (tối ưu render) |
| `source_file_id` | ObjectId → geospatial_files | | File gốc |
| `legal_document_ids` | [ObjectId] | | Căn cứ pháp lý ranh giới |
| `accuracy_m` | double | | Sai số định vị (m) |

> ⚠️ MongoDB 2dsphere yêu cầu tọa độ hợp lệ và **right-hand rule** cho polygon. MultiPolygon lớn (>16MB) phải tách hoặc lưu file gốc ở `geospatial_files` và chỉ giữ hình rút gọn trong Mongo.

### 3.4 `merger_mappings`

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|-------|------|:---:|---------|
| `_id` | ObjectId | ✓ | Khóa sự kiện |
| `operation_type` | enum | ✓ | `merge` (n→1), `split` (1→n), `rename` (1→1), `transfer` (đổi cha), `dissolve` (giải thể), `establish` (lập mới) |
| `effective_date` | date | ✓ | Ngày sự kiện có hiệu lực |
| `level` | enum | ✓ | Cấp diễn ra sự kiện |
| `source_units` | [object] | ✓ | Đơn vị nguồn: `{ unit_id, version_id, name_snapshot, contribution }` |
| `target_units` | [object] | ✓ | Đơn vị đích: `{ unit_id, version_id, name_snapshot }` |
| `legal_document_ids` | [ObjectId] | ✓ | Văn bản căn cứ |
| `description` | string | | Diễn giải |
| `recorded_at` | date | ✓ | Transaction time |

> `name_snapshot` lưu tên tại thời điểm sự kiện để hiển thị nhanh mà không cần join — chấp nhận một chút denormalize có chủ đích.

### 3.5 `address_conversion_rules`

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|-------|------|:---:|---------|
| `_id` | ObjectId | ✓ | Khóa luật |
| `effective_date` | date | ✓ | Ngày luật chuyển đổi áp dụng |
| `mapping_type` | enum | ✓ | `one_to_one`, `many_to_one`, `one_to_many` |
| `old_address` | object | ✓ | `{ province_id, district_id, ward_id, province_name, district_name, ward_name, normalized }` |
| `new_address` | object | ✓ | Cấu trúc tương tự cho địa chỉ mới |
| `resolution` | enum | | Khi `one_to_many`: `geometry_required` (phải dựa hình học/đường phố để xác định đích) |
| `merger_mapping_id` | ObjectId | | Sự kiện sinh ra luật |
| `confidence` | double | | Độ tin cậy (0–1) |
| `verified` | bool | | Đã thẩm định thủ công chưa |
| `notes` | string | | Ghi chú (vd "giữ nguyên số nhà/đường") |

### 3.6 `legal_documents`

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|-------|------|:---:|---------|
| `_id` | ObjectId | ✓ | Khóa |
| `doc_number` | string | ✓ | Số hiệu (vd `Nghị quyết 1234/NQ-UBTVQH15`) |
| `doc_type` | enum | ✓ | `nghi_quyet`, `nghi_dinh`, `quyet_dinh`, `thong_tu` |
| `issuing_body` | string | ✓ | Cơ quan ban hành (Quốc hội, UBTVQH, Chính phủ…) |
| `title` | string | ✓ | Trích yếu |
| `issued_date` | date | ✓ | Ngày ban hành |
| `effective_date` | date | ✓ | Ngày hiệu lực |
| `source_url` | string | | Link công báo/cổng thông tin |
| `file_id` | ObjectId → geospatial_files / GridFS | | File scan |
| `affected_unit_ids` | [ObjectId] | | Các đơn vị bị tác động (đánh chỉ mục để tra cứu nhanh) |

### 3.7 `map_layers`

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|-------|------|:---:|---------|
| `_id` | ObjectId | ✓ | Khóa |
| `layer_code` | string | ✓ | Mã lớp duy nhất (vd `transport`) |
| `name` | string | ✓ | Tên hiển thị |
| `category` | enum | ✓ | `transport`, `urban`, `industrial`, `residential`, `administrative`, `conservation`, `infrastructure` |
| `geometry_type` | enum | ✓ | `polygon` / `line` / `point` |
| `default_style` | object | | `{ fillColor, strokeColor, opacity, zIndex }` |
| `source_type` | enum | ✓ | `internal`, `mapbox`, `google`, `osm`, `wms` |
| `external_config` | object | | Cấu hình nguồn ngoài: `{ tileUrl, styleUrl, apiKeyRef }` |

### 3.8 `planning_maps`

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|-------|------|:---:|---------|
| `_id` | ObjectId | ✓ | Khóa |
| `name` | string | ✓ | Tên đồ án (vd `Quy hoạch tỉnh X thời kỳ 2021–2030, tầm nhìn 2120`) |
| `scope` | enum | ✓ | `national`, `provincial`, `district`, `ward`, `zone` |
| `region_unit_id` | ObjectId → units | | Đơn vị hành chính phạm vi |
| `planning_period` | object | ✓ | `{ from_year, to_year }` |
| `vision_year` | int | | Năm tầm nhìn dài hạn (vd 2125 — tầm nhìn ~100 năm) |
| `approval_status` | enum | ✓ | `draft`, `approved`, `superseded` |
| `legal_document_ids` | [ObjectId] | | Quyết định phê duyệt |
| `version` | int | ✓ | Phiên bản đồ án |
| `valid_from` / `valid_to` | date | ✓ | Hiệu lực đồ án |

### 3.9 `planning_zones`

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|-------|------|:---:|---------|
| `_id` | ObjectId | ✓ | Khóa |
| `planning_map_id` | ObjectId → planning_maps | ✓ | Thuộc đồ án nào |
| `layer_id` | ObjectId → map_layers | ✓ | Thuộc lớp nào |
| `zone_code` | string | | Mã vùng |
| `name` | string | | Tên vùng (vd `KCN Phía Bắc`) |
| `geometry` | GeoJSON Polygon/MultiPolygon | ✓ | Hình học vùng (WGS84) |
| `properties` | object | | Thuộc tính quy hoạch: `{ land_use, density, max_height_m, population_target }` |
| `vision_year` | int | | Mốc tầm nhìn của vùng |
| `valid_from` / `valid_to` | date | ✓ | Hiệu lực |
| `status` | enum | ✓ | `proposed`, `approved`, `built`, `superseded` |

### 3.10 `geospatial_files`

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|-------|------|:---:|---------|
| `_id` | ObjectId | ✓ | Khóa |
| `filename` | string | ✓ | Tên file |
| `format` | enum | ✓ | `shapefile`, `geojson`, `kml`, `gml`, `geotiff`, `gpkg` |
| `storage` | object | ✓ | `{ provider: "s3"|"gridfs", uri, bucket }` |
| `srs` | string | ✓ | Hệ quy chiếu gốc (vd `EPSG:3405` VN2000) |
| `related_entity` | object | | `{ type: "boundary"|"planning_zone", id }` |
| `checksum` | string | | SHA-256 chống trùng/đảm bảo toàn vẹn |
| `size_bytes` | long | | Dung lượng |
| `import_status` | enum | ✓ | `uploaded`, `validated`, `imported`, `failed` |
| `uploaded_by` / `uploaded_at` | | ✓ | Audit |

### 3.11 `audit_logs`

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|-------|------|:---:|---------|
| `_id` | ObjectId | ✓ | Khóa |
| `entity_type` | string | ✓ | Collection bị tác động |
| `entity_id` | ObjectId | ✓ | Bản ghi bị tác động |
| `action` | enum | ✓ | `create`, `update`, `delete`, `merge`, `split`, `version_close` |
| `changed_by` | string | ✓ | User/service thực hiện |
| `changed_at` | date | ✓ | Transaction time |
| `before` / `after` | object | | Diff trước/sau (chỉ field thay đổi) |
| `source_document_id` | ObjectId | | Văn bản căn cứ |
| `reason` | string | | Lý do |

---

## 5. Quan hệ giữa các collection

```
legal_documents ◄───────────┐ (căn cứ pháp lý, many-to-many)
      ▲                      │
      │                      │
administrative_units 1───* administrative_unit_versions
      │  (entity ổn định)        │ parent_unit_id ──► administrative_units
      │                          │ boundary_id ──► administrative_boundaries
      │                          │ merger_mapping_id ─┐
      │                                               │
      ├──1───* administrative_boundaries (GeoJSON)    │
      │                                               ▼
      └──*──◄ merger_mappings (source_units[]/target_units[]) ─► administrative_units
                     │
                     └─► address_conversion_rules (1 sự kiện sinh nhiều luật)

planning_maps 1───* planning_zones *───1 map_layers
      │                  │
      └─ region_unit_id ─┴─► administrative_units / geospatial_files

audit_logs ──► (entity_type, entity_id) trỏ tới mọi collection
geospatial_files ──► boundaries / planning_zones (file gốc)
```

Tóm tắt cardinality:
- 1 unit ⟷ N versions ⟷ N boundaries (theo thời gian).
- 1 merger_mapping ⟷ N source_units & N target_units (nhiều-nhiều).
- N versions ⟷ M legal_documents (nhiều-nhiều, qua mảng id).
- 1 planning_map ⟷ N planning_zones; 1 zone ⟷ 1 layer.

---

## 6. Index

```js
// --- administrative_units ---
db.administrative_units.createIndex({ unit_code: 1 }, { unique: true })
db.administrative_units.createIndex({ status: 1 })

// --- administrative_unit_versions (CỐT LÕI cho temporal) ---
// Point-in-time theo đơn vị
db.administrative_unit_versions.createIndex({ unit_id: 1, valid_from: 1, valid_to: 1 })
// Dựng cây con theo cha tại 1 ngày
db.administrative_unit_versions.createIndex({ parent_unit_id: 1, valid_from: 1, valid_to: 1 })
// Tra theo cấp + thời gian
db.administrative_unit_versions.createIndex({ level: 1, valid_to: 1, valid_from: 1 })
// Khớp địa chỉ theo tên chuẩn hóa
db.administrative_unit_versions.createIndex({ name_normalized: 1, level: 1, valid_to: 1 })
// Lấy version hiện tại nhanh
db.administrative_unit_versions.createIndex({ unit_id: 1, status: 1 })
// Ràng buộc không chồng lấn (partial, version đang mở là duy nhất)
db.administrative_unit_versions.createIndex(
  { unit_id: 1 }, { unique: true, partialFilterExpression: { valid_to: null } }
)

// --- administrative_boundaries (GEOSPATIAL) ---
db.administrative_boundaries.createIndex({ geometry: "2dsphere" })
db.administrative_boundaries.createIndex({ unit_id: 1, valid_from: 1, valid_to: 1 })

// --- merger_mappings ---
db.merger_mappings.createIndex({ "source_units.unit_id": 1, effective_date: 1 })
db.merger_mappings.createIndex({ "target_units.unit_id": 1, effective_date: 1 })
db.merger_mappings.createIndex({ operation_type: 1, level: 1, effective_date: 1 })

// --- address_conversion_rules (tra cứu địa chỉ) ---
db.address_conversion_rules.createIndex({
  "old_address.province_id": 1, "old_address.district_id": 1,
  "old_address.ward_id": 1, effective_date: 1
})
db.address_conversion_rules.createIndex({ "old_address.normalized": 1 })

// --- legal_documents ---
db.legal_documents.createIndex({ doc_number: 1 }, { unique: true })
db.legal_documents.createIndex({ effective_date: 1 })
db.legal_documents.createIndex({ affected_unit_ids: 1 })

// --- planning_zones (GEOSPATIAL) ---
db.planning_zones.createIndex({ geometry: "2dsphere" })
db.planning_zones.createIndex({ planning_map_id: 1, layer_id: 1 })
db.planning_zones.createIndex({ layer_id: 1, vision_year: 1 })

// --- planning_maps ---
db.planning_maps.createIndex({ region_unit_id: 1, approval_status: 1 })

// --- audit_logs ---
db.audit_logs.createIndex({ entity_type: 1, entity_id: 1, changed_at: -1 })
```

**Ghi chú index temporal:** truy vấn point-in-time dạng `valid_from <= D AND (valid_to == null OR valid_to > D)` không lý tưởng cho B-tree (vì range hai phía). Mẹo tối ưu: đặt `valid_to: 1` đứng trước trong index khi lọc các bản ghi "đang mở" (`valid_to: null`), và dùng `{unit_id, valid_from}` cho truy vấn lịch sử rồi lọc `valid_to` ở giai đoạn sau. Với khối lượng lớn, cân nhắc **MongoDB Atlas Search** hoặc materialize "snapshot hiện tại" vào collection riêng.

---

## 7. Document mẫu

### 7.1 administrative_units (đơn vị bị sáp nhập — giữ lịch sử)
```json
{
  "_id": { "$oid": "650000000000000000000a01" },
  "unit_code": "VN-AU-HADONG",
  "country": "VN",
  "nominal_kind": "territory",
  "status": "dissolved",
  "current_version_id": null,
  "created_at": { "$date": "2008-08-01T00:00:00Z" },
  "updated_at": { "$date": "2025-07-01T00:00:00Z" }
}
```

### 7.2 administrative_unit_versions (2 version: cũ và bị đóng)
```json
[
  {
    "_id": { "$oid": "650000000000000000000b01" },
    "unit_id": { "$oid": "650000000000000000000a01" },
    "version_no": 1,
    "name": "Hà Đông",
    "full_name": "Quận Hà Đông",
    "name_normalized": "ha dong",
    "level": "district",
    "unit_type": "quan",
    "parent_unit_id": { "$oid": "650000000000000000000a10" },
    "official_codes": { "gso": "268" },
    "valid_from": { "$date": "2009-05-08T00:00:00Z" },
    "valid_to":   { "$date": "2025-07-01T00:00:00Z" },
    "change_type": "established",
    "legal_document_ids": [ { "$oid": "650000000000000000000d01" } ],
    "boundary_id": { "$oid": "650000000000000000000c01" },
    "merger_mapping_id": null,
    "recorded_at": { "$date": "2020-01-10T00:00:00Z" },
    "status": "superseded"
  }
]
```

### 7.3 administrative_boundaries
```json
{
  "_id": { "$oid": "650000000000000000000c01" },
  "unit_id": { "$oid": "650000000000000000000a01" },
  "version_id": { "$oid": "650000000000000000000b01" },
  "geometry": {
    "type": "MultiPolygon",
    "coordinates": [[[ [105.74,20.95],[105.80,20.95],[105.80,20.99],[105.74,20.99],[105.74,20.95] ]]]
  },
  "centroid": { "type": "Point", "coordinates": [105.77, 20.97] },
  "bbox": [105.74, 20.95, 105.80, 20.99],
  "area_km2": 49.6,
  "valid_from": { "$date": "2009-05-08T00:00:00Z" },
  "valid_to":   { "$date": "2025-07-01T00:00:00Z" },
  "srs": "EPSG:4326",
  "source_file_id": { "$oid": "650000000000000000000f01" },
  "legal_document_ids": [ { "$oid": "650000000000000000000d01" } ]
}
```

### 7.4 merger_mappings (3 phường cũ → 1 phường mới)
```json
{
  "_id": { "$oid": "650000000000000000000e01" },
  "operation_type": "merge",
  "effective_date": { "$date": "2025-07-01T00:00:00Z" },
  "level": "ward",
  "source_units": [
    { "unit_id": { "$oid": "650000000000000000000a21" }, "version_id": { "$oid": "650000000000000000000b21" }, "name_snapshot": "Phường Quang Trung", "contribution": 0.4 },
    { "unit_id": { "$oid": "650000000000000000000a22" }, "version_id": { "$oid": "650000000000000000000b22" }, "name_snapshot": "Phường Yết Kiêu", "contribution": 0.3 },
    { "unit_id": { "$oid": "650000000000000000000a23" }, "version_id": { "$oid": "650000000000000000000b23" }, "name_snapshot": "Phường Nguyễn Trãi", "contribution": 0.3 }
  ],
  "target_units": [
    { "unit_id": { "$oid": "650000000000000000000a30" }, "version_id": { "$oid": "650000000000000000000b30" }, "name_snapshot": "Phường Hà Đông" }
  ],
  "legal_document_ids": [ { "$oid": "650000000000000000000d02" } ],
  "description": "Sáp nhập 3 phường thành phường Hà Đông",
  "recorded_at": { "$date": "2025-06-20T00:00:00Z" }
}
```

### 7.5 address_conversion_rules (n→1)
```json
{
  "_id": { "$oid": "6500000000000000000010a1" },
  "effective_date": { "$date": "2025-07-01T00:00:00Z" },
  "mapping_type": "many_to_one",
  "old_address": {
    "province_id": { "$oid": "650000000000000000000a10" }, "province_name": "Thành phố Hà Nội",
    "district_id": { "$oid": "650000000000000000000a01" }, "district_name": "Quận Hà Đông",
    "ward_id": { "$oid": "650000000000000000000a21" }, "ward_name": "Phường Quang Trung",
    "normalized": "ha noi|ha dong|quang trung"
  },
  "new_address": {
    "province_id": { "$oid": "650000000000000000000a10" }, "province_name": "Thành phố Hà Nội",
    "district_id": null, "district_name": null,
    "ward_id": { "$oid": "650000000000000000000a30" }, "ward_name": "Phường Hà Đông",
    "normalized": "ha noi||ha dong"
  },
  "merger_mapping_id": { "$oid": "650000000000000000000e01" },
  "confidence": 1.0,
  "verified": true,
  "notes": "Bỏ cấp quận; giữ nguyên số nhà và tên đường"
}
```

### 7.6 planning_zones
```json
{
  "_id": { "$oid": "6500000000000000000011a1" },
  "planning_map_id": { "$oid": "6500000000000000000012a1" },
  "layer_id": { "$oid": "6500000000000000000013a1" },
  "zone_code": "KCN-PB-01",
  "name": "Khu công nghiệp Phía Bắc",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[ [105.81,21.05],[105.86,21.05],[105.86,21.09],[105.81,21.09],[105.81,21.05] ]]
  },
  "properties": { "land_use": "industrial", "density": "low", "max_height_m": 45 },
  "vision_year": 2120,
  "valid_from": { "$date": "2024-01-01T00:00:00Z" },
  "valid_to": null,
  "status": "approved"
}
```

---

## 8. Ví dụ query MongoDB

### 8.1 Tìm địa chỉ mới từ địa chỉ cũ
**Cách A — tra theo luật chuyển đổi (nhanh, ưu tiên):**
```js
db.address_conversion_rules.find({
  "old_address.province_id": ObjectId("650000000000000000000a10"),
  "old_address.district_id": ObjectId("650000000000000000000a01"),
  "old_address.ward_id":     ObjectId("650000000000000000000a21"),
  effective_date: { $lte: ISODate("2025-12-31") }
}).sort({ effective_date: -1 }).limit(1)
```

**Cách B — khi không có luật sẵn, suy ra từ merger graph + enrich tên mới:**
```js
db.merger_mappings.aggregate([
  { $match: { "source_units.unit_id": ObjectId("650000000000000000000a21"),
              operation_type: "merge" } },
  { $unwind: "$target_units" },
  { $lookup: {
      from: "administrative_unit_versions",
      let: { uid: "$target_units.unit_id", d: "$effective_date" },
      pipeline: [
        { $match: { $expr: { $and: [
          { $eq: ["$unit_id", "$$uid"] },
          { $lte: ["$valid_from", "$$d"] },
          { $or: [ { $eq: ["$valid_to", null] }, { $gt: ["$valid_to", "$$d"] } ] }
        ]}}}
      ],
      as: "new_unit"
  }},
  { $project: { _id: 0, new_unit_name: { $first: "$new_unit.full_name" },
                effective_date: 1 } }
])
```

### 8.2 Tìm địa giới hành chính tại một ngày cụ thể
```js
const D = ISODate("2015-06-01");
db.administrative_unit_versions.findOne({
  unit_id: ObjectId("650000000000000000000a01"),
  valid_from: { $lte: D },
  $or: [ { valid_to: null }, { valid_to: { $gt: D } } ]
})
```
Lấy toàn bộ đơn vị cấp xã đang tồn tại ngày D:
```js
db.administrative_unit_versions.find({
  level: "ward",
  valid_from: { $lte: D },
  $or: [ { valid_to: null }, { valid_to: { $gt: D } } ]
})
```

### 8.3 Tìm các đơn vị bị sáp nhập vào một đơn vị mới
```js
db.merger_mappings.aggregate([
  { $match: { "target_units.unit_id": ObjectId("650000000000000000000a30"),
              operation_type: "merge" } },
  { $unwind: "$source_units" },
  { $project: { _id: 0,
      source_unit_id: "$source_units.unit_id",
      source_name: "$source_units.name_snapshot",
      contribution: "$source_units.contribution",
      effective_date: 1 } }
])
```

### 8.4 Tìm polygon của một xã/phường (tại ngày D)
```js
db.administrative_boundaries.findOne(
  {
    unit_id: ObjectId("650000000000000000000a30"),
    valid_from: { $lte: D },
    $or: [ { valid_to: null }, { valid_to: { $gt: D } } ]
  },
  { geometry: 1, centroid: 1, area_km2: 1 }
)
```

### 8.5 Tìm các lớp quy hoạch giao với một khu vực
```js
const aoi = {
  type: "Polygon",
  coordinates: [[ [105.80,21.04],[105.87,21.04],[105.87,21.10],[105.80,21.10],[105.80,21.04] ]]
};

db.planning_zones.aggregate([
  { $match: { geometry: { $geoIntersects: { $geometry: aoi } },
              status: "approved" } },
  { $lookup: { from: "map_layers", localField: "layer_id",
               foreignField: "_id", as: "layer" } },
  { $unwind: "$layer" },
  { $group: {
      _id: "$layer.category",
      layer_name: { $first: "$layer.name" },
      zones: { $push: { name: "$name", vision_year: "$vision_year" } },
      count: { $sum: 1 }
  }}
])
```
> Cũng có thể dùng `$geoWithin` (vùng nằm trọn trong AOI) hoặc `$near`/`$geoNear` cho truy vấn theo khoảng cách.

### 8.6 Reverse geocoding theo thời điểm (điểm thuộc xã nào tại ngày D)
```js
db.administrative_boundaries.findOne({
  geometry: { $geoIntersects: { $geometry: { type: "Point", coordinates: [105.77, 20.97] } } },
  valid_from: { $lte: D },
  $or: [ { valid_to: null }, { valid_to: { $gt: D } } ]
})
```

---

## 9. Import dữ liệu từ nguồn chính thống

**Nguồn khuyến nghị:**
- Danh mục đơn vị hành chính & mã số: Tổng cục Thống kê (GSO) — bộ mã chuẩn quốc gia.
- Văn bản pháp lý: Nghị quyết của Quốc hội / Ủy ban Thường vụ Quốc hội, Nghị định/Quyết định của Chính phủ (Công báo, Cổng thông tin điện tử Chính phủ).
- Ranh giới địa lý: shapefile/GeoPackage từ cơ quan tài nguyên–môi trường/đo đạc bản đồ; bổ sung tham chiếu OpenStreetMap khi cần.

**Pipeline ETL (idempotent, có versioning):**
1. **Ingest → staging.** Đẩy file thô vào `geospatial_files` (GridFS/S3), tính checksum để chống import trùng.
2. **Validate.** Kiểm tra GeoJSON hợp lệ (right-hand rule), tọa độ trong VN, mã GSO khớp danh mục.
3. **Reproject.** Chuyển hệ VN2000 (EPSG:3405) → WGS84 (EPSG:4326) bằng GDAL/`ogr2ogr` trước khi nạp (2dsphere yêu cầu WGS84).
4. **Match & version.** Khóa nghiệp vụ = `unit_code + valid_from`. Nếu đơn vị đã tồn tại và có thay đổi → đóng version cũ (`valid_to = effective_date`), tạo version mới; nếu chưa có → tạo entity + version đầu.
5. **Sinh sự kiện.** Từ văn bản pháp lý, tạo `merger_mappings` và phát sinh `address_conversion_rules` tương ứng (đặc biệt cho n→1, 1→n).
6. **Audit.** Mỗi thao tác ghi `audit_logs` với `source_document_id` và diff.
7. **Snapshot (tùy chọn).** Cập nhật `current_version_id` và collection snapshot "hiện tại" để API đọc nhanh.

Công cụ thực thi: `mongoimport` cho dữ liệu phẳng; script Python/Node (pymongo / `mongoose`) + GDAL cho geometry; chạy trong transaction (replica set) để đảm bảo "đóng version cũ + mở version mới" là nguyên tử.

---

## 10. Cấu trúc API backend đề xuất

**Kiến trúc phân tầng:** `API layer (REST/GraphQL)` → `Service layer (nghiệp vụ temporal)` → `Repository layer (Mongo driver)` → `MongoDB`. Tách riêng module geocoding và module render bản đồ.

**Endpoint gợi ý (REST):**

| Method & Path | Chức năng |
|---------------|-----------|
| `GET /units?at=YYYY-MM-DD&level=&parent=` | Danh sách đơn vị tại thời điểm |
| `GET /units/{id}` | Chi tiết entity + version hiện tại |
| `GET /units/{id}/versions` | Toàn bộ lịch sử version |
| `GET /units/{id}/at/{date}` | Version hiệu lực tại ngày |
| `GET /units/{id}/boundary?at=` | GeoJSON ranh giới (hỗ trợ `simplify=zoom`) |
| `GET /units/{id}/children?at=` | Cây con tại thời điểm |
| `GET /units/{id}/mergers` | Sự kiện sáp nhập/tách liên quan |
| `POST /address/convert` | Body: địa chỉ cũ → trả địa chỉ mới (+ fallback geometry) |
| `GET /geocode/reverse?lng=&lat=&at=` | Điểm → đơn vị tại thời điểm |
| `GET /planning/maps?region=&vision=` | Đồ án quy hoạch theo vùng/tầm nhìn |
| `POST /planning/zones/intersect` | Body: GeoJSON AOI → lớp/vùng quy hoạch giao cắt |
| `GET /layers` | Danh mục lớp + style cho frontend |
| `GET /legal-documents/{id}` | Văn bản pháp lý nguồn |

**Lưu ý production:**
- Output luôn chuẩn **GeoJSON FeatureCollection** để Mapbox/Leaflet/Google Maps dùng trực tiếp.
- Cung cấp **vector tiles** (`/tiles/{z}/{x}/{y}.pbf`) cho dataset lớn thay vì trả polygon thô.
- Cache snapshot "hiện tại" (Redis) cho truy vấn không kèm `at`.
- Tham số `at` mặc định = hôm nay; mọi truy vấn lịch sử đều đi qua cùng một service temporal để nhất quán quy ước nửa mở.
- Phân quyền ghi (import/version) tách khỏi quyền đọc; mọi ghi đều phát sinh `audit_logs`.

---

## 11. Trade-off Embedded vs Reference (giải thích lựa chọn)

| Quan hệ | Lựa chọn | Lý do |
|---------|----------|-------|
| Unit ↔ Versions | **Reference** | Số version tăng không giới hạn theo thời gian; cần truy vấn version độc lập theo point-in-time; embedding sẽ làm document phình và phá vỡ giới hạn 16MB. |
| Version ↔ Boundary | **Reference** | Polygon/MultiPolygon rất lớn (có thể vài MB/đơn vị); ranh giới và tên đổi theo nhịp khác nhau; 2dsphere index hoạt động hiệu quả khi geometry ở collection riêng. |
| Merger ↔ source/target units | **Embed (mảng) + reference id** | Tập nguồn/đích có giới hạn (vài–vài chục phần tử), luôn đọc cùng sự kiện. Embed mảng `{unit_id, name_snapshot}` để hiển thị nhanh, nhưng vẫn giữ `unit_id` để join chính xác. |
| Version ↔ Legal documents | **Reference (mảng id)** | Một văn bản tác động nhiều đơn vị (nhiều-nhiều); embed sẽ trùng lặp lớn và khó cập nhật. |
| Planning map ↔ zones | **Reference** | Một đồ án có thể hàng nghìn vùng; cần geospatial query trên từng zone độc lập. |
| Zone ↔ Layer | **Reference** | Layer là danh mục dùng chung, style đổi tập trung. |
| Audit ↔ before/after | **Embed** | Snapshot bất biến, luôn đọc cùng log; không chia sẻ. |
| Unit ↔ official_codes | **Embed (trong version)** | Mã chính thống thay đổi theo thời gian → là thuộc tính của version, gọn và đọc cùng. |

**Nguyên tắc chung áp dụng:** *embed khi dữ liệu bị bao chứa, có giới hạn kích thước, và luôn đọc cùng cha; reference khi dữ liệu tăng trưởng không giới hạn, được chia sẻ nhiều-nhiều, hoặc cần truy vấn/đánh chỉ mục độc lập (đặc biệt geometry và version).*

---

## 12. Checklist tuân thủ yêu cầu

- [x] Tách Administrative Unit (ổn định) ≠ Unit Version (theo thời gian).
- [x] Boundary GeoJSON Polygon/MultiPolygon riêng, có 2dsphere.
- [x] Merger Mapping mô hình cũ→mới nhiều-nhiều, không mất lịch sử.
- [x] Address Conversion Rule đa cấp tỉnh/huyện/xã.
- [x] Planning Layer (danh mục) ≠ Planning Zone (vùng cụ thể).
- [x] Không giả định cấp cố định (`level` ở version, hỗ trợ bỏ cấp huyện).
- [x] Truy vấn theo thời điểm hiệu lực (point-in-time, bi-temporal).
- [x] Audit log + nguồn pháp lý + ngày hiệu lực.
- [x] Mở rộng tích hợp Mapbox/Google/OSM/Leaflet qua `map_layers.external_config` + output GeoJSON/vector tiles.
- [x] Không dùng 1 collection phẳng.
