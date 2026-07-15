export default function Legend() {
  return (
    <div className="legend">
      <div className="legend-item">
        <span className="swatch active" /> Đang hoạt động / sau sáp nhập
      </div>
      <div className="legend-item">
        <span className="swatch inactive" /> Đã sáp nhập / trước sáp nhập
      </div>
      <div className="legend-item">
        <span className="swatch selected" /> Đang chọn
      </div>
    </div>
  );
}
