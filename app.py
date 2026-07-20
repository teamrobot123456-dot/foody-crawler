from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

from foody_client import CrawlerError, crawl_public_reviews, normalize_restaurant_url


st.set_page_config(
    page_title="Cào bình luận Foody",
    page_icon="🍜",
    layout="centered",
)

st.title("🍜 Công cụ thu thập bình luận công khai")
st.write(
    "Dán link **trang quán** từ Foody hoặc ShopeeFood. "
    "Ứng dụng sẽ chuẩn hóa link về trang Foody tương ứng, tải các bình luận công khai "
    "và tạo file Excel."
)
st.caption(
    "Chỉ sử dụng cho mục đích nghiên cứu hợp pháp; không thu thập dữ liệu riêng tư, "
    "không vượt qua đăng nhập và nên giới hạn tần suất truy cập."
)
st.warning(
    "Lưu ý nguồn dữ liệu: ứng dụng xuất **bình luận có nội dung chữ trên Foody**. "
    "Con số như **1,2K đánh giá** trên ShopeeFood thường không đồng nghĩa có 1.200 "
    "bình luận chữ để xuất Excel."
)


def make_excel(rows: list[dict], metadata: dict) -> bytes:
    reviews_df = pd.DataFrame(rows)
    metadata_df = pd.DataFrame(
        [
            {"Thông tin": "Thời điểm xuất file", "Giá trị": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            {"Thông tin": "Nền tảng link đầu vào", "Giá trị": metadata["input_platform"]},
            {"Thông tin": "Link đầu vào", "Giá trị": metadata["input_url"]},
            {"Thông tin": "Link Foody đã xác định", "Giá trị": metadata["foody_url"]},
            {"Thông tin": "Phương thức ánh xạ", "Giá trị": metadata["mapping_method"]},
            {"Thông tin": "Foody ResId", "Giá trị": metadata["res_id"]},
            {"Thông tin": "Chế độ thu thập", "Giá trị": metadata.get("collection_mode", "")},
            {"Thông tin": "Tổng bình luận Foody công bố", "Giá trị": metadata.get("declared_review_count", "")},
            {"Thông tin": "Số bình luận thu thập được", "Giá trị": metadata["review_count"]},
            {"Thông tin": "Phạm vi nguồn", "Giá trị": metadata.get("source_scope", "")},
            {"Thông tin": "Lý do dừng", "Giá trị": metadata["stop_reason"]},
        ]
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        reviews_df.to_excel(writer, index=False, sheet_name="Binh_luan")
        metadata_df.to_excel(writer, index=False, sheet_name="Thong_tin")

        review_sheet = writer.sheets["Binh_luan"]
        review_sheet.freeze_panes = "A2"
        review_sheet.auto_filter.ref = review_sheet.dimensions

        widths = {
            "A": 16,
            "B": 24,
            "C": 16,
            "D": 35,
            "E": 80,
            "F": 22,
            "G": 18,
            "H": 12,
            "I": 55,
            "J": 65,
        }
        for column, width in widths.items():
            review_sheet.column_dimensions[column].width = width

        info_sheet = writer.sheets["Thong_tin"]
        info_sheet.column_dimensions["A"].width = 28
        info_sheet.column_dimensions["B"].width = 100

    return output.getvalue()


with st.form("crawler_form", clear_on_submit=False):
    input_url = st.text_input(
        "Link quán Foody/ShopeeFood",
        placeholder="https://www.foody.vn/ha-noi/ten-quan",
    )
    fetch_all = st.checkbox(
        "Lấy toàn bộ bình luận công khai Foody trả về",
        value=True,
        help=(
            "Ứng dụng sẽ tiếp tục phân trang cho tới khi Foody không còn trả thêm "
            "bình luận. Tổng lượt đánh giá sao trên ShopeeFood có thể lớn hơn số "
            "bình luận văn bản công khai trên Foody."
        ),
    )
    max_reviews = st.number_input(
        "Số bình luận tối đa khi không lấy toàn bộ",
        min_value=10,
        max_value=50000,
        value=500,
        step=50,
        disabled=fetch_all,
    )
    speed_mode = st.selectbox(
        "Tốc độ thu thập",
        options=["Nhanh (khuyến nghị)", "Ổn định", "Rất nhanh"],
        index=0,
        help=(
            "Chế độ nhanh gửi mỗi yêu cầu tối đa 30 bình luận và nghỉ 0,30 giây. "
            "Foody có thể tự giới hạn còn 10 bình luận mỗi phản hồi. Nếu gặp HTTP 429/403, "
            "hãy chuyển sang Ổn định."
        ),
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
        if normalized.input_platform == "ShopeeFood":
            st.info(
                "Ứng dụng sẽ tìm link Foody được ShopeeFood liên kết; nếu không tìm thấy, "
                "ứng dụng thử ánh xạ theo cùng tỉnh/thành và slug. "
                "File kết quả ghi nhận các bình luận văn bản công khai từ Foody."
            )

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
                progress_callback=update_progress,
            )

        if progress_bar is not None:
            progress_bar.progress(1.0)

        if not rows:
            st.warning(
                "Trang quán đã được nhận diện nhưng Foody không trả về bình luận văn bản. "
                "Quán có thể chỉ có điểm sao hoặc endpoint đã thay đổi."
            )
        else:
            declared = metadata.get('declared_review_count')
            if declared:
                st.success(
                    f"Đã thu thập {len(rows)}/{declared} bình luận Foody công bố. "
                    f"Foody ResId: {metadata['res_id']}."
                )
            else:
                st.success(
                    f"Đã thu thập {len(rows)} bình luận. Foody ResId: {metadata['res_id']}."
                )
            st.caption(metadata["stop_reason"])
            st.caption(
                f"Chế độ: {speed_mode} · yêu cầu tối đa {selected_speed['batch']} mục/lượt "
                f"· nghỉ {selected_speed['delay']:.2f} giây giữa các lượt."
            )

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

        with st.expander("Thông tin kỹ thuật"):
            st.json({k: v for k, v in metadata.items() if k != "pagination_diagnostics"})

        with st.expander("Nhật ký phân trang — dùng để kiểm tra trường hợp dừng sớm"):
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
        st.info(
            "Hãy kiểm tra rằng link có dạng trang quán, ví dụ: "
            "https://www.foody.vn/ha-noi/ten-quan. "
            "Không dùng link trang tìm kiếm hoặc link rút gọn."
        )
    except Exception as exc:
        if progress_bar is not None:
            progress_bar.empty()
        progress_text.empty()
        st.exception(exc)
