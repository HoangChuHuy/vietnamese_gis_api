# GIS Admin API — Địa giới hành chính Việt Nam (đợt sáp nhập 07/2025)

Hệ thống tra cứu và quản lý dữ liệu địa giới hành chính Việt Nam quanh đợt sáp nhập tỉnh/xã tháng 7/2025 (mô hình 3 cấp tỉnh–huyện–xã cũ chuyển sang 2 cấp tỉnh–xã mới). Gồm 2 phần:

- **Backend** ([app/](app/)) — FastAPI + Motor (MongoDB async driver), đọc/ghi trực tiếp database `gis_admin` trên MongoDB Atlas.
- **Frontend** ([web/](web/)) — React 18 + TypeScript + Vite, bản đồ tương tác bằng Leaflet/react-leaflet.

> Tài liệu thiết kế mở rộng: [thiet-ke-mongodb-dia-gioi-hanh-chinh.md](thiet-ke-mongodb-dia-gioi-hanh-chinh.md) (mô hình lý thuyết 11 collection bi-temporal) và [de-xuat-api.md](de-xuat-api.md) (khảo sát dữ liệu thực tế trên Atlas — cơ sở cho code hiện tại, vốn được đơn giản hoá còn 4 collection).

## Mục lục

- [Kiến trúc & dữ liệu](#kiến-trúc--dữ-liệu)
- [Cài đặt & chạy](#cài-đặt--chạy)
- [Cấu hình (.env)](#cấu-hình-env)
- [API Reference](#api-reference)
  - [Units — Đơn vị hành chính](#units--đơn-vị-hành-chính)
  - [Boundaries — Ranh giới địa lý](#boundaries--ranh-giới-địa-lý)
  - [Geocode — Tra cứu theo toạ độ](#geocode--tra-cứu-theo-toạ-độ)
  - [Address — Chuyển đổi địa chỉ](#address--chuyển-đổi-địa-chỉ)
  - [Legal documents — Văn bản pháp lý](#legal-documents--văn-bản-pháp-lý)
  - [Audit logs — Nhật ký thay đổi](#audit-logs--nhật-ký-thay-đổi)
- [Frontend: cách tiêu thụ dữ liệu API](#frontend-cách-tiêu-thụ-dữ-liệu-api)
- [Hạn chế đã biết](#hạn-chế-đã-biết)

## Kiến trúc & dữ liệu

```
Client (web/ hoặc bất kỳ HTTP client nào)
        │  REST/JSON, prefix /api
        ▼
FastAPI router  →  service (business logic)  →  Motor (async)  →  MongoDB Atlas (gis_admin)
```

Mỗi router chỉ parse/validate input (qua FastAPI `Query`/Pydantic) rồi gọi thẳng hàm service tương ứng; toàn bộ logic nghiệp vụ (build filter, gọi Mongo, xử lý lỗi, serialize) nằm trong `app/services/*.py`. Không có tầng repository/ORM trung gian — service thao tác trực tiếp bằng Motor `find`/`insert_one`/`update_one`.

### 4 collection MongoDB

| Collection (hằng số trong [app/models/collections.py](app/models/collections.py)) | Vai trò |
|---|---|
| `administrative_units` (`UNITS`) | Danh mục đơn vị hành chính (tỉnh/huyện/xã), quan hệ cha-con qua `parent_code` |
| `administrative_boundaries` (`BOUNDARIES`) | Polygon/MultiPolygon GeoJSON của từng đơn vị, có **2dsphere index trên `geometry`** |
| `legal_documents` (`LEGAL_DOCUMENTS`) | Văn bản pháp lý (Nghị quyết UBTVQH...) làm căn cứ sáp nhập/đổi tên |
| `audit_logs` (`AUDIT_LOGS`) | Lịch sử thay đổi (before/after state) — thay cho collection version riêng |

Tất cả `ObjectId`/`datetime` trong response đều được serialize qua [app/utils/serialization.py](app/utils/serialization.py) (`serialize_doc`/`serialize_docs`) thành `str`/ISO string trước khi trả JSON.

## Cài đặt & chạy

```bash
# Backend
cp .env.example .env        # rồi điền MONGO_URI thật
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # docs: http://127.0.0.1:8000/docs

# Frontend
cd web
npm install
npm run dev                  # http://localhost:5173
```

`run.sh` khởi động song song cả hai (script giả định Python nằm trong 1 conda env cố định — sửa biến `CONDA_ENV_PYTHON` cho đúng máy bạn trước khi dùng).

## Cấu hình (.env)

File `.env` ở gốc repo được dùng chung cho cả backend (đọc bằng `pydantic-settings`) lẫn frontend (Vite đọc nhờ `envDir: '..'` trong [web/vite.config.ts](web/vite.config.ts)):

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `MONGO_URI` | *(bắt buộc)* | Connection string Atlas (`mongodb+srv://...`) |
| `MONGO_DB_NAME` | `gis_admin` | Tên database |
| `API_PREFIX` | `/api` | Tiền tố gắn cho mọi router |
| `DEFAULT_PAGE_SIZE` | `20` | Số bản ghi/trang mặc định |
| `MAX_PAGE_SIZE` | `200` | Giới hạn `limit` tối đa cho phân trang |
| `CORS_ORIGINS` | `*` | Danh sách origin CORS, phân tách bằng dấu phẩy |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000/api` | Base URL frontend gọi vào backend |

## API Reference

Tất cả path bên dưới đã gắn sẵn prefix `/api` (trừ `GET /health`). Không có bất kỳ cơ chế authentication/authorization nào — mọi endpoint, kể cả các thao tác ghi, đều public.

Định dạng phân trang chung (`paginated_response`, [app/utils/pagination.py](app/utils/pagination.py)) cho các endpoint danh sách (trừ `boundaries`, trả `FeatureCollection` riêng):
```json
{ "items": [...], "page": 1, "limit": 20, "total": 123, "total_pages": 7 }
```
`page`/`limit` là query param dùng chung (`page ≥ 1`, `1 ≤ limit ≤ MAX_PAGE_SIZE`); `skip = (page-1) * limit`.

> **Về các ví dụ `curl` bên dưới**: base URL dùng `http://127.0.0.1:8000/api` (server chạy local mặc định). Response mẫu được dựng lại theo đúng cấu trúc field thực tế đã khảo sát trên Atlas ([de-xuat-api.md](de-xuat-api.md) mục 1), dùng code/tên **minh hoạ** (không phải trích xuất trực tiếp từ DB) — hãy thay `code`/`_id`/toạ độ bằng dữ liệu thật khi tự chạy thử.

---

### Units — Đơn vị hành chính

Router: [app/routers/units.py](app/routers/units.py) · Service: [app/services/unit_service.py](app/services/unit_service.py) · Collection: `administrative_units`

#### `GET /api/units`
Liệt kê đơn vị hành chính, có filter kết hợp.

**Query**: `level` (1-3), `type`, `status`, `parent_code`, `q` (tìm theo tên), `page`, `limit`.

**Logic xử lý** (`_build_unit_filter` + `list_units`):
1. Build filter Mongo từ các param có giá trị (bỏ qua param `None`) — filter kiểu "AND" đơn giản: `level`, `type`, `status`, `parent_code` map thẳng thành điều kiện `$eq`.
2. Nếu có `q`: escape regex (`re.escape`) rồi build pattern case-insensitive, gộp thành `$or` trên 3 field `name`, `name_with_type`, `slug`. Đây là tìm kiếm **substring**, không phải full-text index — không cần Mongo text index nhưng sẽ chậm dần khi dữ liệu lớn vì `$or` regex không dùng được index hiệu quả.
3. `count_documents(query)` lấy tổng số để tính `total_pages`.
4. `find(query).sort("code", 1).skip(skip).limit(limit)` — sắp xếp cố định theo `code` tăng dần.
5. Serialize toàn bộ document (bao gồm cả field không khai báo trong Pydantic response — router không dùng `response_model` nên trả nguyên document Mongo, chỉ ẩn field bằng `_to_feature`/`serialize_doc` chuyển kiểu, không lọc field).

**Ví dụ**
```bash
curl "http://127.0.0.1:8000/api/units?level=1&limit=2"
```
```json
{
  "items": [
    {
      "_id": "665f1a2b3c4d5e6f7a8b9c01",
      "code": "01",
      "name": "Hà Nội",
      "slug": "ha-noi",
      "type": "thanh-pho",
      "node_type": "thanh-pho-trung-uong",
      "name_with_type": "Thành phố Hà Nội",
      "path": "Hà Nội",
      "path_with_type": "Thành phố Hà Nội",
      "parent_code": null,
      "parent_id": null,
      "level": 1,
      "status": "active",
      "era": "post_reform",
      "valid_from": "2025-07-01T00:00:00",
      "valid_to": null,
      "legal_document_id": "665f0000112233445566aabb"
    },
    {
      "_id": "665f1a2b3c4d5e6f7a8b9c1e",
      "code": "46",
      "name": "Huế",
      "slug": "hue",
      "type": "thanh-pho",
      "node_type": "thanh-pho-trung-uong",
      "name_with_type": "Thành phố Huế",
      "path": "Huế",
      "path_with_type": "Thành phố Huế",
      "parent_code": null,
      "parent_id": null,
      "level": 1,
      "status": "active",
      "era": "post_reform",
      "valid_from": "2025-07-01T00:00:00",
      "valid_to": null,
      "legal_document_id": "665f0000112233445566aacc"
    }
  ],
  "page": 1,
  "limit": 2,
  "total": 34,
  "total_pages": 17
}
```

#### `GET /api/units/search`
Alias tiện dụng của `list_units` nhưng bắt buộc `q` (không rỗng). Nội bộ gọi thẳng `list_units(db, pagination, q=q)` — **không truyền `level`/`type`/...**, nên search luôn tìm trên toàn bộ collection bất kể cấp.

**Ví dụ**
```bash
curl "http://127.0.0.1:8000/api/units/search?q=hue&limit=1"
```
```json
{
  "items": [
    {
      "_id": "665f1a2b3c4d5e6f7a8b9c1e",
      "code": "46",
      "name": "Huế",
      "slug": "hue",
      "type": "thanh-pho",
      "name_with_type": "Thành phố Huế",
      "parent_code": null,
      "level": 1,
      "status": "active"
    }
  ],
  "page": 1,
  "limit": 1,
  "total": 1,
  "total_pages": 1
}
```

#### `GET /api/units/{code}`
`find_one({"code": code})`. Không tìm thấy → `404` với message `Không tìm thấy đơn vị hành chính với code={code}`.

**Ví dụ**
```bash
curl "http://127.0.0.1:8000/api/units/01"
```
```json
{
  "_id": "665f1a2b3c4d5e6f7a8b9c01",
  "code": "01",
  "name": "Hà Nội",
  "slug": "ha-noi",
  "type": "thanh-pho",
  "node_type": "thanh-pho-trung-uong",
  "name_with_type": "Thành phố Hà Nội",
  "path": "Hà Nội",
  "path_with_type": "Thành phố Hà Nội",
  "parent_code": null,
  "level": 1,
  "status": "active",
  "era": "post_reform",
  "valid_from": "2025-07-01T00:00:00",
  "valid_to": null,
  "legal_document_id": "665f0000112233445566aabb"
}
```
Trường hợp không tìm thấy:
```bash
curl -i "http://127.0.0.1:8000/api/units/00000"
```
```
HTTP/1.1 404 Not Found
{"detail":"Không tìm thấy đơn vị hành chính với code=00000"}
```

#### `GET /api/units/{code}/children`
`find({"parent_code": code})`, filter thêm `status` nếu có, sort theo `code`. Đây là quan hệ cha-con **1 cấp** (không đệ quy) — muốn lấy cháu phải gọi lại endpoint này với code con.

**Ví dụ**
```bash
curl "http://127.0.0.1:8000/api/units/01/children?status=active&limit=2"
```
```json
{
  "items": [
    {
      "_id": "665f1a2b3c4d5e6f7a8b9d10",
      "code": "00001",
      "name": "Ba Đình",
      "type": "phuong",
      "name_with_type": "Phường Ba Đình",
      "parent_code": "01",
      "level": 3,
      "status": "active"
    },
    {
      "_id": "665f1a2b3c4d5e6f7a8b9d11",
      "code": "00004",
      "name": "Hoàn Kiếm",
      "type": "phuong",
      "name_with_type": "Phường Hoàn Kiếm",
      "parent_code": "01",
      "level": 3,
      "status": "active"
    }
  ],
  "page": 1,
  "limit": 2,
  "total": 126,
  "total_pages": 63
}
```

#### `GET /api/units/{code}/history`
Không đọc từ `administrative_units` mà query `audit_logs`: `{"$or": [{"before_state.code": code}, {"after_state.code": code}]}`, sort `valid_from` giảm dần. Vì `restructure` (xem dưới) là nguồn ghi duy nhất vào `audit_logs` với `entity_type="unit"`, endpoint này thực chất trả lịch sử các lần `restructure` đã áp dụng lên unit đó (và các unit có code trùng xuất hiện trong before/after state của record khác, nếu có).

**Ví dụ**
```bash
curl "http://127.0.0.1:8000/api/units/71/history?limit=1"
```
```json
{
  "items": [
    {
      "_id": "665f2b3c4d5e6f7a8b9c0d01",
      "entity_type": "unit",
      "action": "merge",
      "valid_from": "2025-07-01T00:00:00",
      "valid_to": null,
      "system_from": "2025-06-15T09:12:31",
      "system_to": null,
      "created_by": "api",
      "legal_document_id": "665f0000112233445566aabb",
      "before_state": { "code": "71", "name": "Bến Tre", "status": "active" },
      "after_state": { "target_codes": ["71-new"] },
      "change_summary": "Sáp nhập Bến Tre theo Nghị quyết UBTVQH đợt 07/2025"
    }
  ],
  "page": 1,
  "limit": 1,
  "total": 1,
  "total_pages": 1
}
```

#### `POST /api/units` (201)
Tạo 1 đơn vị mới.
1. Check trùng `code` → `409` nếu đã tồn tại.
2. `model_dump()` toàn bộ payload, gắn `created_at`/`updated_at` = `datetime.now(timezone.utc)`.
3. `insert_one`, sau đó `find_one` lại bằng `inserted_id` để trả về document đầy đủ (bao gồm `_id` string hoá).

**Ví dụ**
```bash
curl -X POST "http://127.0.0.1:8000/api/units" \
  -H "Content-Type: application/json" \
  -d '{
        "code": "99999",
        "name": "Demo",
        "type": "xa",
        "level": 3,
        "parent_code": "01",
        "status": "active"
      }'
```
```json
{
  "_id": "665f3c4d5e6f7a8b9c0d1e2f",
  "code": "99999",
  "name": "Demo",
  "slug": null,
  "type": "xa",
  "node_type": null,
  "name_with_type": null,
  "path": null,
  "path_with_type": null,
  "parent_code": "01",
  "level": 3,
  "status": "active",
  "created_at": "2026-07-16T10:20:31.512000",
  "updated_at": "2026-07-16T10:20:31.512000"
}
```
Nếu `code` đã tồn tại: `HTTP 409 {"detail": "code=99999 đã tồn tại"}`.

#### `POST /api/units/bulk` (201)
Tạo hàng loạt (`UnitBulkCreate`, tối đa 2000 phần tử). Logic **không transaction, không fail-fast**:
1. Query 1 lần `find({"code": {"$in": codes}})` để lấy tập `existing_codes`.
2. Duyệt từng unit trong payload: nếu `code` đã tồn tại trong DB **hoặc** đã xuất hiện trước đó trong chính request (trùng lặp nội bộ, theo dõi bằng set `seen`) → đẩy vào danh sách `skipped`, không insert.
3. Các unit còn lại được `insert_many` **một lần duy nhất** ở cuối.
4. Trả về `{requested, inserted, skipped: [code,...], skipped_reason}` — cho phép client biết chính xác bản ghi nào bị bỏ qua mà không làm fail toàn bộ batch.

**Ví dụ**
```bash
curl -X POST "http://127.0.0.1:8000/api/units/bulk" \
  -H "Content-Type: application/json" \
  -d '{
        "units": [
          {"code": "99999", "name": "Demo 1", "type": "xa", "level": 3, "parent_code": "01"},
          {"code": "88888", "name": "Demo 2", "type": "xa", "level": 3, "parent_code": "01"}
        ]
      }'
```
```json
{
  "requested": 2,
  "inserted": 1,
  "skipped": ["99999"],
  "skipped_reason": "code đã tồn tại hoặc trùng lặp trong request"
}
```

#### `POST /api/units/{code}/restructure`
Nghiệp vụ **tái cơ cấu** đơn vị hành chính — endpoint duy nhất ghi vào `audit_logs` cho `entity_type="unit"`. Không có bảng version riêng: mọi thay đổi trạng thái được ghi lại dưới dạng 1 audit log `before_state`/`after_state`.

Logic theo `action` (`RestructureRequest`):
- **`rename`**: bắt buộc `new_name` (422 nếu thiếu). `update_one($set: {name, updated_at})`. `after_state` = `before_state` merge với field vừa đổi.
- **`merge` / `split`**: bắt buộc `target_codes` không rỗng (422 nếu thiếu). Set `status = "inactive"` trên chính unit đang xử lý (unit gốc coi như "đóng" sau khi sáp nhập/tách). `after_state = {"target_codes": [...]}` — **lưu ý: các unit đích trong `target_codes` KHÔNG được tạo/cập nhật tự động** bởi endpoint này; đó là trách nhiệm của client gọi `POST /units` hoặc `/units/bulk` riêng.
- **`dissolve`**: tương tự merge/split nhưng không yêu cầu `target_codes` — chỉ set `status = "inactive"`.

Sau khi update, insert 1 document vào `audit_logs`:
```json
{
  "entity_type": "unit", "action": "<merge|split|rename|dissolve>",
  "valid_from": "<effective_date hoặc now>", "valid_to": null,
  "system_from": "<now>", "system_to": null,
  "created_by": "api",
  "legal_document_id": "<từ payload, optional>",
  "before_state": {...toàn bộ doc trước khi update...},
  "after_state": {...tuỳ action...},
  "change_summary": "<payload.reason hoặc message mặc định>"
}
```
Trả về document unit **sau khi update** (`find_one` lại). Không có rollback nếu insert audit log thất bại sau khi đã update unit (không dùng Mongo transaction).

**Ví dụ**
```bash
curl -X POST "http://127.0.0.1:8000/api/units/71/restructure" \
  -H "Content-Type: application/json" \
  -d '{
        "action": "merge",
        "target_codes": ["71-new"],
        "legal_document_id": "665f0000112233445566aabb",
        "effective_date": "2025-07-01T00:00:00",
        "reason": "Sáp nhập theo Nghị quyết UBTVQH đợt 07/2025"
      }'
```
```json
{
  "_id": "665f1a2b3c4d5e6f7a8b9c71",
  "code": "71",
  "name": "Bến Tre",
  "type": "tinh",
  "level": 1,
  "status": "inactive",
  "updated_at": "2026-07-16T10:22:05.118000"
}
```

---

### Boundaries — Ranh giới địa lý

Router: [app/routers/boundaries.py](app/routers/boundaries.py) · Service: [app/services/boundary_service.py](app/services/boundary_service.py) · Collection: `administrative_boundaries`

Mọi response ở đây là **GeoJSON Feature/FeatureCollection** — hàm nội bộ `_to_feature(doc)` tách field `geometry` ra khỏi document, phần còn lại (đã serialize) đưa vào `properties`:
```json
{ "type": "Feature", "geometry": {...}, "properties": { "unit_code": "...", "province_name": "...", ... } }
```

#### `GET /api/boundaries`
**Query**: `province_code`, `level`, `era` (`pre_reform`/`post_reform`), `status`, `page`, `limit`.

Build filter `$eq` theo các param có giá trị (giống pattern của units), `count_documents` lấy `total`, `find(query).skip().limit()` — **không có `sort()`** (thứ tự trả về phụ thuộc thứ tự lưu trữ tự nhiên của Mongo, không đảm bảo ổn định tuyệt đối giữa các lần gọi). Trả về:
```json
{ "type": "FeatureCollection", "features": [...], "page": 1, "limit": 200, "total": 3821 }
```

**Ví dụ**
```bash
curl "http://127.0.0.1:8000/api/boundaries?province_code=01&era=post_reform&limit=1"
```
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "MultiPolygon",
        "coordinates": [[[[105.834, 21.028], [105.836, 21.030], [105.833, 21.031], [105.834, 21.028]]]]
      },
      "properties": {
        "_id": "665f4a5b6c7d8e9f0a1b2c01",
        "unit_id": "665f1a2b3c4d5e6f7a8b9d10",
        "unit_code": "00001",
        "unit_name": "Ba Đình",
        "unit_name_with_type": "Phường Ba Đình",
        "unit_type": "phuong",
        "level": 3,
        "status": "active",
        "province_code": "01",
        "province_name": "Hà Nội",
        "district_code": null,
        "district_name": null,
        "parent_code": "01",
        "bbox": [105.80, 21.01, 105.86, 21.05],
        "srs": "EPSG:4326",
        "era": "post_reform",
        "valid_from": "2025-07-01T00:00:00",
        "valid_to": null,
        "source": "GSO",
        "recorded_at": "2025-06-20T08:00:00",
        "merged_into_code": null,
        "geometry_repaired": false
      }
    }
  ],
  "page": 1,
  "limit": 1,
  "total": 126
}
```

#### `GET /api/boundaries/{unit_code}`
**Query**: `era` optional. `find_one({"unit_code": ..., ["era": ... nếu có]}, sort=[("recorded_at", -1)])` — lấy bản ghi **mới nhất** theo `recorded_at` nếu có nhiều version cho cùng `unit_code`/`era`. Không tìm thấy → `404`.

**Ví dụ**
```bash
curl "http://127.0.0.1:8000/api/boundaries/00001?era=post_reform"
```
```json
{
  "type": "Feature",
  "geometry": { "type": "MultiPolygon", "coordinates": [[[[105.834, 21.028], [105.836, 21.030], [105.833, 21.031], [105.834, 21.028]]]] },
  "properties": {
    "_id": "665f4a5b6c7d8e9f0a1b2c01",
    "unit_code": "00001",
    "unit_name": "Ba Đình",
    "unit_name_with_type": "Phường Ba Đình",
    "level": 3,
    "status": "active",
    "province_code": "01",
    "province_name": "Hà Nội",
    "era": "post_reform",
    "merged_into_code": null
  }
}
```
Không tìm thấy: `HTTP 404 {"detail": "Không tìm thấy ranh giới cho unit_code=00001"}`.

#### `POST /api/boundaries` (201)
1. `_prepare_geometry(geometry, auto_fix)`:
   - Gọi `validate_geojson_geometry` ([app/utils/geometry.py](app/utils/geometry.py)) — dựng `shapely.geometry.shape()` từ GeoJSON rồi kiểm `geom.is_valid` (GEOS topology check, bắt lỗi self-intersection, ring không đóng, v.v.).
   - Nếu hợp lệ → dùng nguyên geometry.
   - Nếu **không** hợp lệ và `auto_fix=false` (mặc định) → trả `422` kèm message giải thích lỗi (`explain_validity`) và gợi ý gửi lại với `auto_fix=true`.
   - Nếu không hợp lệ và `auto_fix=true` → gọi `fix_self_intersection`: `geom.buffer(0)` (kỹ thuật GIS chuẩn để "làm sạch" polygon tự cắt, tương đương `ST_Buffer(geom, 0)` trong PostGIS), dùng geometry đã sửa.
2. Build document: toàn bộ field trừ `geometry`/`auto_fix` (`model_dump(exclude=...)`), gắn `geometry` đã xử lý và `recorded_at = now(UTC)`.
3. `insert_one`, `find_one` lại, trả về dạng Feature.

**Lưu ý quan trọng**: request KHÔNG tự kiểm tra field liên quan (`province_code`, `district_code`, `level`...) có khớp với `unit_code` trong `administrative_units` hay không — schema `BoundaryCreate` chấp nhận các field này rời rạc, client tự chịu trách nhiệm điền đúng.

**Ví dụ**
```bash
curl -X POST "http://127.0.0.1:8000/api/boundaries" \
  -H "Content-Type: application/json" \
  -d '{
        "unit_code": "99999",
        "geometry": {
          "type": "Polygon",
          "coordinates": [[[105.80, 21.00], [105.82, 21.00], [105.82, 21.02], [105.80, 21.02], [105.80, 21.00]]]
        },
        "era": "post_reform",
        "source": "manual-import",
        "auto_fix": false
      }'
```
```json
{
  "type": "Feature",
  "geometry": { "type": "Polygon", "coordinates": [[[105.80, 21.00], [105.82, 21.00], [105.82, 21.02], [105.80, 21.02], [105.80, 21.00]]] },
  "properties": {
    "_id": "665f5b6c7d8e9f0a1b2c3d02",
    "unit_code": "99999",
    "era": "post_reform",
    "status": "active",
    "source": "manual-import",
    "recorded_at": "2026-07-16T10:25:44.201000"
  }
}
```
Nếu geometry tự cắt và `auto_fix=false`:
```
HTTP 422
{"detail": "Geometry không hợp lệ (topology): Self-intersection at or near point 105.81 21.01. Gửi lại với auto_fix=true để tự sửa bằng buffer(0), hoặc sửa geometry thủ công."}
```

#### `POST /api/boundaries/bulk` (201)
Tương tự `units/bulk` về triết lý "không fail cả batch", nhưng khác cơ chế lỗi: duyệt từng phần tử, gọi `_prepare_geometry` riêng lẻ; phần tử lỗi topology (và `auto_fix=false`) bị đẩy vào `failed: [{index, unit_code, error}]`, các phần tử hợp lệ được gom lại rồi `insert_many` **một lần** ở cuối. Trả về `{requested, inserted, failed}`.

**Ví dụ**
```bash
curl -X POST "http://127.0.0.1:8000/api/boundaries/bulk" \
  -H "Content-Type: application/json" \
  -d '{
        "boundaries": [
          {"unit_code": "99999", "geometry": {"type": "Polygon", "coordinates": [[[105.80,21.00],[105.82,21.00],[105.82,21.02],[105.80,21.02],[105.80,21.00]]]}, "era": "post_reform"},
          {"unit_code": "88888", "geometry": {"type": "Polygon", "coordinates": [[[105.90,21.00],[105.90,21.02],[105.92,21.01],[105.90,21.00]]]}, "era": "post_reform"}
        ]
      }'
```
```json
{
  "requested": 2,
  "inserted": 1,
  "failed": [
    { "index": 1, "unit_code": "88888", "error": "Ring Self-intersection at or near point 105.91 21.01" }
  ]
}
```

#### `POST /api/boundaries/intersect`
Tìm mọi ranh giới **giao cắt về mặt không gian** với 1 vùng AOI (Area of Interest) do client gửi lên.

**Body** (`IntersectRequest`): `geometry` (Polygon/MultiPolygon), `province_code?`, `level?`, `status?` (mặc định `"active"` — set tường minh trong schema, khác với các filter khác luôn mặc định `None`).

**Logic**: build `{"geometry": {"$geoIntersects": {"$geometry": <AOI>}}}` — dùng trực tiếp toán tử geospatial MongoDB (yêu cầu **2dsphere index** trên `geometry`, đã có sẵn trên collection này), cộng thêm filter `province_code`/`level`/`status` nếu khác `None`. `find(query).to_list(length=1000)` — **giới hạn cứng 1000 kết quả**, không phân trang, không cảnh báo nếu bị cắt bớt.

**Ví dụ**
```bash
curl -X POST "http://127.0.0.1:8000/api/boundaries/intersect" \
  -H "Content-Type: application/json" \
  -d '{
        "geometry": {
          "type": "Polygon",
          "coordinates": [[[105.80, 21.01], [105.85, 21.01], [105.85, 21.04], [105.80, 21.04], [105.80, 21.01]]]
        },
        "province_code": "01",
        "status": "active"
      }'
```
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "MultiPolygon", "coordinates": [ "..." ] },
      "properties": { "unit_code": "00001", "unit_name": "Ba Đình", "province_code": "01", "status": "active" }
    }
  ],
  "total": 1
}
```

#### Hàm dùng chung: `reverse_geocode(db, lng, lat)`
Nằm trong `boundary_service` (không phải `geocode_service`) vì thao tác trực tiếp trên `administrative_boundaries`. Query:
```python
{"geometry": {"$geoIntersects": {"$geometry": {"type": "Point", "coordinates": [lng, lat]}}}, "status": "active"}
```
`find_one` — chỉ trả **1 kết quả đầu tiên** khớp point-in-polygon (không xử lý trường hợp điểm nằm trên biên giữa 2 polygon hợp lệ chồng lấn, nếu dữ liệu có lỗi chồng lấn thì kết quả phụ thuộc thứ tự lưu trữ Mongo). Trả `None` nếu không có polygon `active` nào chứa điểm — được 2 router khác nhau (`geocode.py`, `geocode_service.py`) tái sử dụng và xử lý "not found" theo 2 cách khác nhau (xem mục Geocode).

---

### Geocode — Tra cứu theo toạ độ

Router: [app/routers/geocode.py](app/routers/geocode.py) · Service: [app/services/geocode_service.py](app/services/geocode_service.py)

#### `GET /api/geocode/reverse`
**Query**: `lng` (-180..180), `lat` (-90..90) — validate range ngay ở tầng FastAPI `Query(..., ge=..., le=...)`.

Gọi `boundary_service.reverse_geocode`. Nếu `None` → router tự raise `HTTPException(404, "Không tìm thấy đơn vị hành chính chứa điểm này")`. Đây là **single-point lookup, fail cứng** — client phải tự bắt lỗi 404.

**Ví dụ**
```bash
curl "http://127.0.0.1:8000/api/geocode/reverse?lng=105.834&lat=21.028"
```
```json
{
  "type": "Feature",
  "geometry": { "type": "MultiPolygon", "coordinates": [ "..." ] },
  "properties": {
    "unit_code": "00001",
    "unit_name": "Ba Đình",
    "unit_name_with_type": "Phường Ba Đình",
    "province_code": "01",
    "province_name": "Hà Nội",
    "status": "active",
    "era": "post_reform"
  }
}
```
Không tìm thấy (VD toạ độ ngoài lãnh thổ):
```bash
curl -i "http://127.0.0.1:8000/api/geocode/reverse?lng=0&lat=0"
```
```
HTTP/1.1 404 Not Found
{"detail":"Không tìm thấy đơn vị hành chính chứa điểm này"}
```

#### `POST /api/geocode/reverse/batch`
**Body** (`ReverseGeocodeBatchRequest`): `points: GeoPoint[]` (tối đa 500 điểm, mỗi điểm validate range như trên qua Pydantic `Field`).

**Logic** (`geocode_service.reverse_geocode_batch`): **loop tuần tự**, gọi `reverse_geocode` cho từng điểm — **không dùng `$facet`/aggregation song song**, nghĩa là N điểm = N round-trip Mongo tuần tự (có thể chậm với batch lớn vì không tận dụng được I/O bất đồng bộ song song). Với mỗi điểm, trả về:
```json
{ "lng": ..., "lat": ..., "found": true|false, "feature": {...} | null }
```
Khác với endpoint single-point: batch **không raise lỗi** khi 1 điểm không tìm thấy — set `found: false, feature: null` cho điểm đó và tiếp tục xử lý các điểm còn lại, tránh làm fail toàn bộ batch vì 1 điểm nằm ngoài dữ liệu.

**Ví dụ**
```bash
curl -X POST "http://127.0.0.1:8000/api/geocode/reverse/batch" \
  -H "Content-Type: application/json" \
  -d '{
        "points": [
          {"lng": 105.834, "lat": 21.028},
          {"lng": 0, "lat": 0}
        ]
      }'
```
```json
[
  {
    "lng": 105.834,
    "lat": 21.028,
    "found": true,
    "feature": {
      "type": "Feature",
      "geometry": { "type": "MultiPolygon", "coordinates": [ "..." ] },
      "properties": { "unit_code": "00001", "unit_name": "Ba Đình", "province_code": "01" }
    }
  },
  { "lng": 0, "lat": 0, "found": false, "feature": null }
]
```

---

### Address — Chuyển đổi địa chỉ

Router: [app/routers/address.py](app/routers/address.py) · Service: [app/services/address_service.py](app/services/address_service.py)

#### `POST /api/address/convert`
Chuyển 1 mã đơn vị hành chính **cũ** (trước sáp nhập) sang đơn vị **mới** tương ứng.

**Body** (`AddressConvertRequest`): `province_code?`, `district_code?`, `ward_code?` — validator Pydantic (`model_validator(mode="after")`) bắt buộc có ít nhất 1 field, nếu không → `422`.

**Logic** (`convert_address`):
1. Chọn `old_code` theo thứ tự ưu tiên **ward > district > province** (`payload.ward_code or payload.district_code or payload.province_code`) — nếu client gửi cả 3, chỉ mã cấp thấp nhất (chi tiết nhất) được dùng, 2 mã còn lại bị bỏ qua hoàn toàn.
2. Song song tra `administrative_units.find_one({"code": old_code})` và `administrative_boundaries.find_one({"unit_code": old_code})`.
3. Quyết định `new_unit` theo 2 nhánh:
   - Nếu **boundary có `merged_into_code`** → đây là tín hiệu đáng tin cậy nhất rằng đơn vị đã bị sáp nhập; tra tiếp `administrative_units` theo `merged_into_code` để lấy unit mới, `resolution_note` giải thích rõ nguồn suy luận.
   - Ngược lại, nếu **unit cũ vẫn `status == "active"`** → coi như không có gì thay đổi, `new_unit = old_unit`.
   - Nếu không rơi vào 2 trường hợp trên (VD: unit đã `inactive` nhưng boundary không có `merged_into_code`) → `new_unit = None`, `resolved = false`, kèm message "Không tìm thấy dữ liệu sáp nhập cho mã này."
4. Trả về `{input_code, old_unit, new_unit, resolved, note}` — **luôn HTTP 200** kể cả khi không giải quyết được (không có 404), client phải tự kiểm tra field `resolved`.

**Ví dụ**
```bash
curl -X POST "http://127.0.0.1:8000/api/address/convert" \
  -H "Content-Type: application/json" \
  -d '{"ward_code": "00256"}'
```
```json
{
  "input_code": "00256",
  "old_unit": {
    "_id": "665f1a2b3c4d5e6f7a8b9e56",
    "code": "00256",
    "name": "Yên Phụ",
    "name_with_type": "Phường Yên Phụ",
    "level": 3,
    "status": "inactive"
  },
  "new_unit": {
    "_id": "665f1a2b3c4d5e6f7a8b9d10",
    "code": "00001",
    "name": "Ba Đình",
    "name_with_type": "Phường Ba Đình",
    "level": 3,
    "status": "active"
  },
  "resolved": true,
  "note": "Đã sáp nhập vào đơn vị mã 00001 (theo administrative_boundaries.merged_into_code)."
}
```
Trường hợp không giải quyết được:
```json
{
  "input_code": "00999",
  "old_unit": null,
  "new_unit": null,
  "resolved": false,
  "note": "Không tìm thấy dữ liệu sáp nhập cho mã này."
}
```

---

### Legal documents — Văn bản pháp lý

Router: [app/routers/legal_documents.py](app/routers/legal_documents.py) · Service: [app/services/legal_document_service.py](app/services/legal_document_service.py) · Collection: `legal_documents`

#### `GET /api/legal-documents`
**Query**: `province_code` (khớp field lồng `scope.province_code`), `doc_type`, `date_from`/`date_to` (khoảng `effective_date`, dùng `$gte`/`$lte`), `page`, `limit`. Sort theo `effective_date` giảm dần (văn bản mới nhất trước).

**Ví dụ**
```bash
curl "http://127.0.0.1:8000/api/legal-documents?doc_type=nghi-quyet&limit=1"
```
```json
{
  "items": [
    {
      "_id": "665f0000112233445566aabb",
      "doc_number": "NQ-1234/2025/UBTVQH15",
      "number": "1234",
      "serial": "2025",
      "doc_type": "nghi-quyet",
      "issuing_body_code": "ubtvqh",
      "issuing_body": "Ủy ban Thường vụ Quốc hội",
      "issue_date": "2025-06-15T00:00:00",
      "effective_date": "2025-07-01T00:00:00",
      "title": "Nghị quyết về việc sắp xếp đơn vị hành chính cấp tỉnh, cấp xã năm 2025",
      "scope": { "level": "quoc-gia", "province_code": null, "province_name": null },
      "units_affected": 3321,
      "raw_reference": "https://vanban.chinhphu.vn/...",
      "created_at": "2025-06-20T08:00:00"
    }
  ],
  "page": 1,
  "limit": 1,
  "total": 37,
  "total_pages": 37
}
```

#### `GET /api/legal-documents/{doc_id}`
`doc_id` là **ObjectId string** (không phải `doc_number`). `_parse_object_id` bắt `InvalidId` → `422` nếu format sai; không tìm thấy → `404`.

**Ví dụ**
```bash
curl "http://127.0.0.1:8000/api/legal-documents/665f0000112233445566aabb"
```
```json
{
  "_id": "665f0000112233445566aabb",
  "doc_number": "NQ-1234/2025/UBTVQH15",
  "doc_type": "nghi-quyet",
  "issuing_body": "Ủy ban Thường vụ Quốc hội",
  "issue_date": "2025-06-15T00:00:00",
  "effective_date": "2025-07-01T00:00:00",
  "title": "Nghị quyết về việc sắp xếp đơn vị hành chính cấp tỉnh, cấp xã năm 2025",
  "units_affected": 3321
}
```
`doc_id` sai định dạng: `HTTP 422 {"detail": "id không hợp lệ: abc"}`.

#### `GET /api/legal-documents/{doc_id}/units`
Trả danh sách unit bị ảnh hưởng bởi văn bản: query `administrative_units.find({"legal_document_id": doc_id})` — so khớp **string** `doc_id` với field `legal_document_id` lưu trên từng unit (được set khi tạo/restructure unit, không tự động backfill). Endpoint chỉ validate format `doc_id` (không check văn bản có tồn tại hay không) trước khi query.

**Ví dụ**
```bash
curl "http://127.0.0.1:8000/api/legal-documents/665f0000112233445566aabb/units?limit=1"
```
```json
{
  "items": [
    { "_id": "665f1a2b3c4d5e6f7a8b9c71", "code": "71", "name": "Bến Tre", "level": 1, "status": "inactive", "legal_document_id": "665f0000112233445566aabb" }
  ],
  "page": 1,
  "limit": 1,
  "total": 3321,
  "total_pages": 3321
}
```

#### `POST /api/legal-documents` (201)
Check trùng `doc_number` → `409` nếu đã tồn tại. Gắn `created_at`, `insert_one`, trả lại document đầy đủ.

**Ví dụ**
```bash
curl -X POST "http://127.0.0.1:8000/api/legal-documents" \
  -H "Content-Type: application/json" \
  -d '{
        "doc_number": "NQ-9999/2026/UBTVQH15",
        "doc_type": "nghi-quyet",
        "issuing_body": "Ủy ban Thường vụ Quốc hội",
        "issue_date": "2026-07-01T00:00:00",
        "effective_date": "2026-08-01T00:00:00",
        "title": "Văn bản demo"
      }'
```
```json
{
  "_id": "665f6c7d8e9f0a1b2c3d4e05",
  "doc_number": "NQ-9999/2026/UBTVQH15",
  "doc_type": "nghi-quyet",
  "issuing_body": "Ủy ban Thường vụ Quốc hội",
  "issue_date": "2026-07-01T00:00:00",
  "effective_date": "2026-08-01T00:00:00",
  "title": "Văn bản demo",
  "created_at": "2026-07-16T10:30:12.004000"
}
```

---

### Audit logs — Nhật ký thay đổi

Router: [app/routers/audit_logs.py](app/routers/audit_logs.py) · Service: [app/services/audit_log_service.py](app/services/audit_log_service.py) · Collection: `audit_logs`

#### `GET /api/audit-logs`
**Query**: `entity_type`, `action`, `date_from`/`date_to` (khoảng `valid_from`), `page`, `limit`. Sort `valid_from` giảm dần. Đây là endpoint **generic** — không giới hạn theo unit cụ thể, dùng để rà soát toàn bộ lịch sử hệ thống. (Không có endpoint `POST` — audit log chỉ được ghi gián tiếp qua `units/{code}/restructure`.)

**Ví dụ**
```bash
curl "http://127.0.0.1:8000/api/audit-logs?entity_type=unit&action=merge&limit=1"
```
```json
{
  "items": [
    {
      "_id": "665f2b3c4d5e6f7a8b9c0d01",
      "entity_type": "unit",
      "action": "merge",
      "valid_from": "2025-07-01T00:00:00",
      "valid_to": null,
      "system_from": "2025-06-15T09:12:31",
      "system_to": null,
      "created_by": "api",
      "legal_document_id": "665f0000112233445566aabb",
      "before_state": { "code": "71", "name": "Bến Tre", "status": "active" },
      "after_state": { "target_codes": ["71-new"] },
      "change_summary": "Sáp nhập Bến Tre theo Nghị quyết UBTVQH đợt 07/2025"
    }
  ],
  "page": 1,
  "limit": 1,
  "total": 3247,
  "total_pages": 3247
}
```

Hàm `get_unit_history` (dùng bởi `GET /api/units/{code}/history`) nằm trong cùng service này — xem mục Units ở trên.

---

## Frontend: cách tiêu thụ dữ liệu API

Toàn bộ gọi API tập trung ở [web/src/api/](web/src/api/), qua 1 wrapper duy nhất [client.ts](web/src/api/client.ts):

```ts
apiGet<T>(path, params) // fetch GET, tự build query string, bỏ qua param undefined/""
```
Điểm đáng chú ý trong wrapper: **404 không throw** — trả `null as T` thẳng cho caller, còn mọi status lỗi khác mới `throw Error`. Điều này cho phép các hàm gọi `getBoundary`/`reverseGeocode` coi "không tìm thấy" là kết quả hợp lệ (`null`) thay vì phải try/catch ở mọi nơi gọi.

### `api/units.ts` → dùng bởi [Sidebar.tsx](web/src/components/Sidebar.tsx)

- **`listProvinces()`**: gọi `GET /units?level=1&limit=100`, sau đó **khử trùng client-side** bằng `Map<code, unit>` — vì dữ liệu nguồn có vài tỉnh trùng `code` do đổi tên trong đợt sáp nhập (VD Thừa Thiên Huế → Huế) chưa được dọn ở tầng DB; giữ bản ghi *xuất hiện sau cùng* trong response (ghi đè theo thứ tự duyệt `Map.set`), rồi sort theo `name_with_type` bằng `localeCompare(..., "vi")` để đúng thứ tự chữ cái tiếng Việt. Kết quả đổ vào `<select>` chọn tỉnh trong Sidebar, load 1 lần khi mount (`useEffect([])`).
- **`searchUnits(q, limit=20)`**: Sidebar debounce 300ms bằng `setTimeout`/`clearTimeout` trong `useEffect([query])`, chỉ gọi khi `query.trim().length >= 2`. Kết quả đổ vào dropdown `<ul class="search-results">`; click 1 kết quả gọi `onSelectSearchResult` (xử lý ở `App.tsx`, xem bên dưới) rồi xoá query.
- **`getChildren(code)`**: gọi từ đâu đó cần liệt kê con trực tiếp — hiện **không được UI nào trong repo gọi trực tiếp** (chỉ export sẵn), khác với việc lọc `districtFilter` trong `App.tsx` vốn tính từ chính `features` (boundaries) đã tải, không gọi endpoint này.
- **`getHistory(code)`**: gọi từ [UnitDetailPanel.tsx](web/src/components/UnitDetailPanel.tsx) khi bấm "Xem lịch sử thay đổi" — `GET /units/{code}/history?limit=50`, kết quả `AuditLog[]` render thành danh sách `{action, valid_from (format vi-VN qua `toLocaleDateString`), change_summary}`.

### `api/boundaries.ts` → dùng bởi [useBoundaries.ts](web/src/hooks/useBoundaries.ts), `App.tsx`

- **`listBoundaries({provinceCode, level, era, status})`**: **tự động gộp trang** — gọi `GET /boundaries` lặp lại với `page` tăng dần, `limit=200` cố định mỗi trang, dừng khi: đã lấy đủ `data.total`, HOẶC trang trả về ít hơn `PAGE_LIMIT` (nghĩa là hết dữ liệu), HOẶC đã đạt trần cứng `MAX_FEATURES = 2000` (an toàn tránh tải cả nước vào bản đồ nếu lỡ không truyền `provinceCode`). Kết quả là 1 mảng `BoundaryFeature[]` phẳng, không còn thông tin phân trang.
- **`getBoundary(unitCode, era?)`**: 1 lần gọi `GET /boundaries/{unitCode}`, trả `BoundaryFeature | null` (404 → null nhờ wrapper).
- **Hook `useProvinceWards(provinceCode, era)`** (dùng trong `App.tsx`): wrap `listBoundaries({provinceCode, era})` trong `useEffect`, có flag `cancelled` để tránh race condition khi user đổi tỉnh liên tục trước khi request cũ trả về (set state chỉ khi `!cancelled`). Ghi chú quan trọng trong code: **cố tình không filter theo `level`** vì `administrative_boundaries` chỉ lưu polygon cấp xã (không có polygon huyện/tỉnh riêng) và field `level` không nhất quán trên dữ liệu thật — nên lấy toàn bộ xã của 1 tỉnh chỉ dựa vào `province_code` + `era`; lọc theo huyện được làm **hoàn toàn phía client** (xem `App.tsx`).

### `api/geocode.ts`

- **`reverseGeocode(lng, lat)`**: `GET /geocode/reverse`, trả `BoundaryFeature | null`.

### Luồng state chính trong [App.tsx](web/src/App.tsx)

`App.tsx` là nơi duy nhất giữ state toàn cục và điều phối dữ liệu giữa các API call với UI:

1. **Tải danh sách xã của 1 tỉnh**: `useProvinceWards(provinceCode, era)` → `features`. Khi `districtFilter` được set, `displayedFeatures = features.filter(f => f.properties.district_code === districtFilter)` — lọc **thuần client-side** trên dữ liệu đã tải, không gọi lại API. `districts` (danh sách huyện cho dropdown) cũng suy ra bằng `useMemo` từ chính `features` (gom `district_code` → `district_name` duy nhất, sort theo tên) — hoàn toàn không có endpoint `/districts` riêng, huyện chỉ tồn tại như thuộc tính đính kèm trên boundary xã.

2. **Chọn kết quả tìm kiếm** (`handleSelectSearchResult`, nhận `AdministrativeUnit` từ `searchUnits`):
   - Nếu `unit.level === 1` (tỉnh) → chuyển thẳng sang chọn tỉnh đó (`handleSelectProvince`), không cần gọi thêm API.
   - Ngược lại, thử `getBoundary(unit.code, era)` — nếu có → `focusOnFeature` (set làm `selectedFeature` + `focusFeature`, đồng thời **đồng bộ ngược** `provinceCode`/`districtFilter`/`era` từ chính `feature.properties` trả về, đảm bảo UI luôn nhất quán với dữ liệu vừa nhận chứ không phải suy đoán trước).
   - Nếu không có boundary và `unit.level === 2` (huyện, cấp đã bị xoá sau sáp nhập nên không có polygon riêng) → chuyển sang xem danh sách xã thuộc huyện đó bằng cách set `provinceCode = unit.parent_code` + `districtFilter = unit.code` (tái dùng cơ chế lọc huyện phía client ở bước 1).
   - Nếu vẫn không khớp trường hợp nào → hiển thị `notFoundMsg` báo không có dữ liệu ranh giới.

3. **Xem đơn vị đã sáp nhập vào** (`handleViewMergedInto`, gọi từ nút trong `UnitDetailPanel`): lấy `merged_into_code` từ `feature.properties` hiện tại (field này backend trả kèm sẵn trong `BoundaryProperties`, không cần gọi thêm `address/convert`) → `getBoundary(code, "post_reform")` (cứng `era="post_reform"` vì đơn vị đích luôn thuộc kỳ sau sáp nhập) → `focusOnFeature` nếu tìm thấy.

4. **Tra cứu theo toạ độ** (`handleMapClick`, chỉ active khi `reverseGeocodeMode = true`, bật qua checkbox ở Sidebar): click bản đồ ([MapView.tsx](web/src/components/MapView.tsx) bắt sự kiện qua `useMapEvents` trong `ClickCatcher`) → `reverseGeocode(lng, lat)` → `focusOnFeature` nếu có kết quả, ngược lại set `notFoundMsg`.

5. **`focusOnFeature`** là điểm hội tụ chung cho 3 luồng trên (search/merged-into/click bản đồ): set `selectedFeature` (để `UnitDetailPanel` hiển thị chi tiết) + `focusFeature` (để `MapView` `flyToBounds` phóng tới khu vực đó) + đồng bộ `provinceCode`/`districtFilter`/`era`. `App.tsx` còn có 1 `useEffect` dọn dẹp: nếu `focusFeature` hoá ra đã nằm trong `displayedFeatures` (layer chính đang render) thì set `focusFeature = null` để tránh `MapView` vẽ đè 2 layer GeoJSON cho cùng 1 polygon (1 từ layer chính, 1 từ layer highlight riêng).

### [MapView.tsx](web/src/components/MapView.tsx) — render GeoJSON

- Nhận `features: BoundaryFeature[]` (đã lọc từ `App.tsx`) và render thành 1 layer `<GeoJSON>` duy nhất của react-leaflet, với `key` là chuỗi nối tất cả `unit_code` — buộc React tạo lại layer khi tập feature thay đổi (react-leaflet không tự re-diff GeoJSON data theo prop thay đổi).
- **Style theo dữ liệu**: `baseStyle(feature)` đọc `properties.era`/`properties.status` để tô màu — `pre_reform`/`inactive` → cam nét đứt (`#f97316`), còn lại (đang hoạt động/sau sáp nhập) → xanh dương (`#2563eb`). Feature đang `selectedCode` được highlight riêng (vàng, viền dày hơn) qua hàm `styleFn` so khớp `unit_code`.
- **`onEachFeature`** gắn listener click cho từng polygon: nếu không ở `reverseGeocodeMode`, click gọi `onSelectUnit(feature.properties.unit_code)` (trỏ tới `handleSelectUnit` ở `App.tsx`, tìm lại feature tương ứng trong `features` hiện có — không gọi API mới vì dữ liệu đã có sẵn trên client).
- **`FitToFeatures`**: tự động `map.fitBounds()` mỗi khi tập `features` (theo tỉnh/huyện) thay đổi, dùng `L.geoJSON(...).getBounds()` tính từ chính dữ liệu GeoJSON nhận được — không cần backend trả `bbox` cấp tỉnh riêng (dù `BoundaryProperties.bbox` có tồn tại ở cấp từng đơn vị).
- **`FlyToFocus`**: riêng cho `focusFeature` (kết quả search/geocode/merged-into) — bay mượt (`flyToBounds`, `maxZoom: 13`) tới đúng polygon đó, tách biệt với việc fit toàn bộ layer chính.

### [Breadcrumb.tsx](web/src/components/Breadcrumb.tsx), [Legend.tsx](web/src/components/Legend.tsx)

- `Breadcrumb` không gọi API — chỉ đọc `feature.properties.{province_name, district_name, unit_name_with_type}` của `selectedFeature` hiện tại để dựng đường dẫn điều hướng; click từng mắt breadcrumb gọi ngược lại callback trong `App.tsx` (`onNavigateProvince`/`onNavigateDistrict`) để đổi state, tận dụng lại dữ liệu boundaries đã tải thay vì gọi lại API.
- `Legend` là component tĩnh (chú giải màu sắc), không liên quan tới dữ liệu API.

## Hạn chế đã biết

- **Không có test, không có authentication/authorization** trên bất kỳ endpoint nào (kể cả write/bulk/restructure).
- **Không có Docker**; `run.sh` cứng đường dẫn Python của 1 máy cụ thể.
- Trường temporal (`era`, `valid_from`/`valid_to`) trên `administrative_units` chỉ phủ khoảng 22% bản ghi (theo khảo sát trong `de-xuat-api.md`); nhiều nghiệp vụ (VD `units/{code}/history`) phụ thuộc hoàn toàn vào `audit_logs` được ghi từ trước, không tự suy luận lại từ dữ liệu thô.
- `POST /boundaries/intersect` giới hạn cứng 1000 kết quả, không phân trang, không cảnh báo khi bị cắt bớt.
- `POST /geocode/reverse/batch` xử lý tuần tự từng điểm (N round-trip Mongo), không tối ưu song song.
- Frontend hiện chỉ tiêu thụ 1 phần tập API: chưa có UI cho `legal-documents`, `audit-logs` (danh sách toàn hệ thống), `address/convert`, `boundaries/intersect`, `units/bulk`, `boundaries/bulk`, `units/{code}/restructure` — các endpoint này chỉ dùng được qua gọi trực tiếp (`/docs` Swagger UI hoặc client khác).
