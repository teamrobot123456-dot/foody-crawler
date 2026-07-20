from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

from foody_client import CrawlerError, crawl_public_reviews, normalize_restaurant_url


st.set_page_config(page_title="Cào bình luận Foody", page_icon="🍜", layout="centered")
st.title("🍜 Công cụ thu thập bình luận công khai")
st.write(
    "Dán link trang quán từ Foody hoặc ShopeeFood. Ứng dụng chuẩn hóa về Foody, "
    "tải các bình luận công khai và tạo file Excel."
)
st.caption(
    "Chỉ sử dụng cho nghiên cứu hợp pháp; không thu thập dữ liệu riêng tư và không vượt đăng nhập."
)
st.warning(
    "Con số hiển thị như 1.3K là số bình luận Foody công bố. Endpoint công khai có thể chỉ "
    "trả một phần lịch sử; ứng dụng sẽ báo rõ số công bố và số thực lấy được."
)


def make_excel(rows: list[dict], metadata: dict) -> bytes:
    reviews_df = pd.DataFrame(rows)
    metadata_rows = [
        {"Thông tin": "Thời điểm xuất file", "Giá trị": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Thông tin": "Nền tảng link đầu vào", "Giá trị": metadata["input_platform"]},
        {"Thông tin": "Link đầu vào", "Giá trị": metadata["input_url"]},
        {"Thông tin": "Link Foody", "Giá trị": metadata["foody_url"]},
        {"Thông tin": "Foody ResId", "Giá trị": metadata["res_id"]},
        {"Thông tin": "Tổng Foody công bố", "Giá trị": metadata.get("declared_review_count", "")},
        {"Thông tin": "Nguồn xác định tổng", "Giá trị": metadata.get("declared_count_source", "")},
        {"Thông tin": "Phân nhóm đánh giá", "Giá trị": str(metadata.get("review_breakdown", {}))},
        {"Thông tin": "Số thu thập được", "Giá trị": metadata["review_count"]},
        {"Thông tin": "Quét mở rộng Type", "Giá trị": metadata.get("probe_review_types", False)},
        {"Thông tin": "Lý do dừng", "Giá trị": metadata["stop_reason"]},
    ]
    metadata_df = pd.DataFrame(metadata_rows)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        reviews_df.to_excel(writer, index=False, sheet_name="Binh_luan")
        metadata_df.to_excel(writer, index=False, sheet_name="Thong_tin")
        review_sheet = writer.sheets["Binh_luan"]
        review_sheet.freeze_panes = "A2"
        review_sheet.auto_filter.ref = review_sheet.dimensions
        widths = {"A": 16, "B": 24, "C": 16, "D": 35, "E": 80, "F": 22, "G": 18, "H": 12, "I": 55, "J": 65}
        for column, width in widths.items():
            review_sheet.column_dimensions[column].width = width
        info_sheet = writer.sheets["Thong_tin"]
        info_sheet.column_dimensions["A"].width = 30
        info_sheet.column_dimensions["B"].width = 110
    return output.getvalue()


with st.form("crawler_form", clear_on_submit=False):
    input_url = st.text_input(
        "Link quán Foody/ShopeeFood",
        placeholder="https://www.foody.vn/ha-noi/ten-quan",
    )
    fetch_all = st.checkbox("Lấy toàn bộ bình luận công khai Foody trả về", value=True)
    max_reviews = st.number_input(
        "Số bình luận tối đa khi không lấy toàn bộ",
        min_value=10,
        max_value=50000,
        value=500,
        step=50,
        disabled=fetch_all,
    )
    probe_review_types = st.checkbox(
        "Quét mở rộng các luồng/nhóm bình luận",
        value=True,
        help=(
            "Khi luồng chuẩn dừng khoảng 200 mục, ứng dụng thử thêm các giá trị Type công khai "
            "và gộp theo mã bình luận. Chậm hơn nhưng có thể lấy thêm dữ liệu."
        ),
    )
    speed_mode = st.selectbox(
        "Tốc độ thu thập",
        options=["Nhanh (khuyến nghị)", "Ổn định", "Rất nhanh"],
        index=0,
    )
    submitted = st.form_submit_button("Bắt đầu thu thập", type="primary")


if submitted:
    progress_text = st.empty()
    progress_bar = st.progress(0) if not fetch_all else None
    selected_max_reviews = None if fetch_all else int(max_reviews)
    speed_settings = {
        "Ổn định": {"delay": 0.8, "batch": 10},
        "Nhanh (khuyến nghị)": {"delay": 0.30, "batch": 30},
        "Rất nhanh": {"delay": 0.15, "batch": 50},
    }
    selected_speed = speed_settings[speed_mode]

    try:
        normalized = normalize_restaurant_url(input_url)

        def update_progress(current_count: int) -> None:
            progress_text.write(f"Đã nhận {current_count} bình luận...")
            if progress_bar is not None and selected_max_reviews:
                progress_bar.progress(min(current_count / selected_max_reviews, 1.0))

        with st.spinner("Đang mở trang quán và tải bình luận..."):
            rows, metadata = crawl_public_reviews(
                raw_url=input_url,
                max_reviews=selected_max_reviews,
                delay_seconds=selected_speed["delay"],
                batch_size=selected_speed["batch"],
                probe_review_types=probe_review_types,
                progress_callback=update_progress,
            )

        if progress_bar is not None:
            progress_bar.progress(1.0)

        declared = metadata.get("declared_review_count")
        breakdown = metadata.get("review_breakdown") or {}
        if declared:
            st.success(
                f"Đã thu thập {len(rows)}/{declared:,} bình luận Foody công bố. "
                f"Foody ResId: {metadata['res_id']}."
            )
            st.caption(f"Nguồn tổng: {metadata.get('declared_count_source', '')}")
        else:
            st.success(f"Đã thu thập {len(rows)} bình luận. Foody ResId: {metadata['res_id']}.")

        if breakdown:
            st.write("Phân nhóm Foody công bố:", breakdown)

        if declared and len(rows) < declared:
            st.warning(metadata["stop_reason"])
        else:
            st.caption(metadata["stop_reason"])

        st.caption(
            f"Chế độ: {speed_mode} · tối đa {selected_speed['batch']} mục/lượt · "
            f"nghỉ {selected_speed['delay']:.2f} giây · quét mở rộng: {probe_review_types}."
        )

        if rows:
            preview_df = pd.DataFrame(rows)
            st.dataframe(
                preview_df[["Tên người dùng", "Điểm đánh giá", "Ngày đăng", "Nội dung bình luận"]].head(20),
                use_container_width=True,
                hide_index=True,
            )
            excel_data = make_excel(rows, metadata)
            safe_slug = normalized.restaurant_slug[:80]
            st.download_button(
                "📥 Tải file Excel",
                data=excel_data,
                file_name=f"binh_luan_{safe_slug}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
        else:
            st.warning("Foody không trả về bình luận văn bản trong phiên này.")

        with st.expander("Thông tin kỹ thuật"):
            st.json({k: v for k, v in metadata.items() if k != "pagination_diagnostics"})

        with st.expander("Nhật ký phân trang"):
            diagnostics = metadata.get("pagination_diagnostics", [])
            if diagnostics:
                st.dataframe(pd.DataFrame(diagnostics), use_container_width=True, hide_index=True)
            else:
                st.write("Không có nhật ký phân trang.")

    except CrawlerError as exc:
        if progress_bar is not None:
            progress_bar.empty()
        progress_text.empty()
        st.error(str(exc))
    except Exception as exc:
        if progress_bar is not None:
            progress_bar.empty()
        progress_text.empty()
        st.exception(exc)
