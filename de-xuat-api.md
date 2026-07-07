# Đề xuất API — GIS Admin Database (MongoDB Atlas)

> Dựa trên kết nối và khảo sát thực tế database `gis_admin` trên cluster Atlas (không phải theo thiết kế lý thuyết trong `thiet-ke-mongodb-dia-gioi-hanh-chinh.md`, vốn có 11 collection — bản đang chạy thực tế đã được đơn giản hoá còn 4 collection).

## 1. Khảo sát dữ liệu thực tế

| Collection | Số docs | Vai trò thực tế |
|---|---|---|
| `administrative_units` | 14,827 | Danh sách tỉnh/huyện/xã (`level` 1/2/3), có `code`, `parent_code`, `status`, và một phần đã gắn temporal (`era`, `valid_from/valid_to`, `legal_document_id` — mới có ở ~3,321 bản ghi thuộc đợt sáp nhập 2025) |
| `administrative_boundaries` | 13,644 | Ranh giới GeoJSON (`MultiPolygon`), có `centroid` (2dsphere index), `era` (`pre_reform`/`post_reform`), `merged_into_code` (6,417 bản ghi trỏ sang đơn vị mới sau sáp nhập) |
| `legal_documents` | 37 | Nghị quyết UBTVQH về sắp xếp đơn vị hành chính (đợt 07/2025) |
| `audit_logs` | 11,506 | Nhật ký thay đổi, có `before_state`/`after_state`, đóng vai trò lịch sử temporal thay cho collection `administrative_unit_versions` riêng |

### Field mẫu

- `administrative_units`: `_id, code, name, slug, type, node_type, name_with_type, path, path_with_type, parent_code, parent_id, level, status, era?, valid_from?, valid_to?, legal_document_id?`
- `administrative_boundaries`: `_id, unit_id, unit_code, unit_name, unit_name_with_type, unit_type, level, status, province_code, province_name, district_code, district_name, parent_code, parent_id, geometry (GeoJSON), centroid, bbox, srs, era, valid_from, valid_to, source, recorded_at, merged_into_code`
- `legal_documents`: `_id, doc_number, number, serial, doc_type, issuing_body_code, issuing_body, issue_date, effective_date, title, scope {level, province_code, province_name}, units_affected, raw_reference, created_at`
- `audit_logs`: `_id, entity_type, action, valid_from, valid_to, system_from, system_to, created_by, legal_document_id, before_state, after_state, change_summary`

### Index hiện có

```js
// administrative_units
{_id:1} | {valid_from:1} | {code:1} | {parent_id:1} | {parent_code:1} | {level:1}
{node_type:1} | {status:1} | {era:1} | {level:1, era:1} | {code:1, level:1}
{slug:1} | {legal_document_id:1}

// administrative_boundaries
{_id:1} | {unit_id:1, valid_from:1, valid_to:1} | {unit_code:1, era:1}
{province_code:1} | {era:1} | {level:1, era:1} | {status:1} | {centroid: "2dsphere"}

// legal_documents
{_id:1} | {issuing_body_code:1} | {scope.province_code:1} | {doc_number:1}

// audit_logs
{_id:1} | {before_state.unit_id:1} | {before_state.code:1} | {entity_type:1}
{action:1} | {legal_document_id:1} | {valid_from:1}
```

## 2. Bảo mật (quan trọng, cần xử lý trước)

Connection string (bao gồm username/password) đã bị dán ở dạng plain text trong chat. Khuyến nghị:

- Đổi mật khẩu user Atlas ngay (Database Access → Edit user).
- Truyền connection string qua biến môi trường (`.env`, không commit lên git).
- Tách 2 user Mongo riêng: một chỉ có quyền `read` cho các API GET, một có quyền `readWrite` giới hạn cho API ghi.

## 3. Kiến trúc đề xuất

```
Express routes → Service (business logic) → Mongo driver/Mongoose → gis_admin
```

## 4. API GET (đọc dữ liệu)

| Method & Path | Query params | Mô tả |
|---|---|---|
| `GET /api/units` | `level, type, status, parent_code, province_code, q, page, limit` | Danh sách đơn vị hành chính, lọc + phân trang (bắt buộc vì có 14.8k bản ghi) |
| `GET /api/units/:code` | | Chi tiết 1 đơn vị theo `code` |
| `GET /api/units/:code/children` | `status` | Danh sách con trực tiếp (`parent_code = code`) |
| `GET /api/units/:code/path` | | Trả `path_with_type` dựng sẵn hoặc leo `parent_id` để dựng breadcrumb |
| `GET /api/units/search` | `q` (bắt buộc) | Tìm theo `name`/`slug`/`name_with_type` (cần text index) |
| `GET /api/boundaries/:unit_code` | `era` | GeoJSON Feature ranh giới mới nhất (hoặc theo `era=pre_reform/post_reform`) |
| `GET /api/boundaries` | `province_code, level, era, status` | FeatureCollection ranh giới theo khu vực/cấp |
| `GET /api/geocode/reverse` | `lng, lat` | Đơn vị hành chính chứa 1 điểm toạ độ (point-in-polygon) |
| `GET /api/units/:code/history` | | Lịch sử thay đổi của 1 đơn vị, lấy từ `audit_logs` theo `before_state.code`/`code` |
| `GET /api/audit-logs` | `entity_type, action, from, to, page, limit` | Nhật ký thay đổi, lọc theo loại thực thể/hành động/khoảng thời gian |
| `GET /api/legal-documents` | `province_code, doc_type, from, to` | Danh sách văn bản pháp lý |
| `GET /api/legal-documents/:id` | | Chi tiết văn bản + `units_affected` |
| `GET /api/legal-documents/:id/units` | | Các đơn vị bị ảnh hưởng bởi văn bản này (join qua `legal_document_id`) |

## 5. API POST (ghi dữ liệu)

| Method & Path | Body | Mô tả |
|---|---|---|
| `POST /api/units` | `{code, name, type, level, parent_code, ...}` | Tạo đơn vị hành chính mới |
| `POST /api/units/:code/restructure` | `{action: "merge"\|"split"\|"rename", target_codes[], legal_document_id, effective_date}` | Thực hiện sáp nhập/tách/đổi tên — đóng bản ghi cũ (`status: inactive`, `valid_to`), tạo bản ghi mới, và tự động ghi `audit_logs` |
| `POST /api/boundaries` | `{unit_code, geometry (GeoJSON), era, valid_from, source}` | Thêm ranh giới mới cho 1 đơn vị |
| `POST /api/legal-documents` | `{doc_number, doc_type, issuing_body, issue_date, effective_date, title, scope}` | Thêm văn bản pháp lý mới |
| `POST /api/address/convert` | `{province_code, district_code?, ward_code}` | Tra `merged_into_code` trong `administrative_boundaries` + `audit_logs.before_state` để trả địa chỉ mới tương ứng |
| `POST /api/geocode/reverse/batch` | `{points: [{lng,lat}, ...]}` | Reverse-geocode nhiều điểm cùng lúc |
| `POST /api/units/bulk` | `{units: [UnitCreate, ...]}` | Tạo nhiều đơn vị cùng lúc (import), bỏ qua `code` trùng/đã tồn tại và báo cáo lại |
| `POST /api/boundaries/bulk` | `{boundaries: [BoundaryCreate, ...]}` | Tạo nhiều ranh giới cùng lúc, validate geometry từng phần tử (shapely), báo lỗi riêng cho từng bản ghi lỗi thay vì fail cả batch |
| `POST /api/boundaries/intersect` | `{geometry (GeoJSON AOI), province_code?, level?, status?}` | Tìm tất cả ranh giới giao cắt với 1 vùng AOI tuỳ ý — dùng `$geoIntersects` trên index `geometry_2dsphere` |

## 6. Lưu ý kỹ thuật khi triển khai

1. ~~Thiếu 2dsphere index trên `geometry`~~ — **đã tạo xong** (`db.administrative_boundaries.createIndex({geometry: "2dsphere"})`). Xem mục 7 để biết quá trình xử lý sự cố khi build index.
2. **Phân trang bắt buộc** cho `/units`, `/audit-logs`, `/boundaries` vì số lượng bản ghi lớn, và geometry mỗi document có thể khá nặng.
3. **Tách quyền đọc/ghi**: GET dùng user Mongo chỉ có `read`, POST dùng user riêng có `readWrite` — hạn chế rủi ro nếu API bị lộ.
4. Field temporal (`era`, `valid_from/valid_to`, `legal_document_id`) mới chỉ phủ ~22% bản ghi `administrative_units` (3,321/14,827) — API `/history` và `/restructure` cần xử lý trường hợp đơn vị chưa có dữ liệu temporal (dữ liệu trước đợt cải cách 07/2025).

## 7. Nhật ký xử lý sự cố: build 2dsphere index thất bại

Khi chạy `db.administrative_boundaries.createIndex({geometry: "2dsphere"})` lần đầu, lệnh báo lỗi `Location16755: Can't extract geo keys` và dừng ngay khi quét tới bản ghi lỗi đầu tiên.

**Nguyên nhân:** 24/13,644 bản ghi (0.18%) có polygon tự cắt chính nó (self-intersecting), phần lớn do lỗi làm tròn toạ độ khi convert shapefile → GeoJSON hoặc khi simplify hình học. Đã loại trừ các nguyên nhân khác: ring không đóng, toạ độ ngoài phạm vi, winding order sai (right-hand rule) — tất cả 13,644 bản ghi đều hợp lệ ở các tiêu chí này.

Danh sách 24 đơn vị bị lỗi: tập trung nhiều ở Lào Cai (7 xã, địa hình núi phức tạp), còn lại rải rác ở Thái Nguyên, Quảng Ninh, Hưng Yên, Bến Tre, An Giang, Hậu Giang, Bạc Liêu, Quảng Trị, Phú Thọ, Hải Phòng, Bà Rịa - Vũng Tàu, TP. Hồ Chí Minh.

**Cách sửa đã áp dụng:**
1. Backup `geometry` gốc của 24 bản ghi vào collection `administrative_boundaries_geometry_backup` trước khi ghi đè (có thể khôi phục nếu cần).
2. Dùng kỹ thuật GIS chuẩn `buffer(0)` (tương đương `ST_Buffer(geom, 0)` trong PostGIS) qua thư viện `@turf/jsts` (JTS port sang JS) để tự sửa polygon tự cắt — 7/24 bản ghi được sửa ngay ở bước này.
3. 17 bản ghi còn lại vẫn bị công cụ kiểm tra `turf.kinks()` báo lỗi sau `buffer(0)`, nhưng xác minh trực tiếp bằng cách thử build index thật trên MongoDB (ground truth) cho thấy MongoDB **chấp nhận** các hình học này — `turf.kinks()` báo dương tính giả (false positive) với các polygon có ranh giới chạm nhau đúng 1 điểm (topology hợp lệ nhưng không phải "simple" theo nghĩa chặt của turf).
4. 1 bản ghi cuối (xã Trung Chải, Lào Cai, mã `03010`) sau `buffer(0)` vẫn bị MongoDB từ chối do để lại một mảnh hình học suy biến (sliver) cực nhỏ — sửa bằng kỹ thuật buffer khứ hồi (`buffer(+ε)` rồi `buffer(-ε)` với ε = 1e-9 độ, chênh lệch diện tích 0%).
5. Build lại index trên toàn bộ collection → **thành công**, index `geometry_2dsphere` đã tồn tại.

Tất cả 24 bản ghi được đánh dấu `geometry_repaired: true` kèm `geometry_repair_note` và `geometry_repaired_at` để truy vết. Geometry gốc vẫn còn nguyên trong `administrative_boundaries_geometry_backup` nếu nhóm muốn đối chiếu hoặc sửa lại bằng tay (QGIS) cho chính xác hơn về mặt địa lý — kỹ thuật `buffer(0)` đảm bảo hình học hợp lệ về mặt topology nhưng có thể làm tròn nhẹ các góc/cạnh tại điểm tự cắt.
