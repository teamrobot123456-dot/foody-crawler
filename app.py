import streamlit as st
import requests
import pandas as pd
import time
import re
from io import BytesIO

# Cấu hình giao diện
st.set_page_config(page_title="Công Cụ Cào Dữ Liệu", page_icon="🍜")
st.title("🍜 Siêu Công Cụ Cào Dữ Liệu")

def get_id_from_html(url):
    """Thử lấy ID bằng cách đọc trực tiếp HTML"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        # Tìm các pattern ID phổ biến
        patterns = [r'"restaurant_id":\s*(\d+)', r'"delivery_id":\s*(\d+)', r'restaurant/(\d+)']
        for p in patterns:
            match = re.search(p, r.text)
            if match: return match.group(1)
    except:
        pass
    return None

input_data = st.text_input("Dán link quán tại đây:", placeholder="Ví dụ: https://www.foody.vn/ha-noi/banh-mi-sot-vang-dinh-ngang")

res_id = None
if input_data:
    with st.spinner("Đang thử tìm ID tự động..."):
        res_id = get_id_from_html(input_data)
        if not res_id:
            st.error("Máy tính không tự tìm được ID. Mẹ làm ơn nhập thủ công giúp con với!")

# Tầng cứu hộ: Nếu không tìm thấy, cho phép nhập tay
if not res_id:
    manual_id = st.text_input("Nhập ID quán (lấy từ mã nguồn trang web):")
    if manual_id:
        res_id = manual_id

if res_id:
    st.success(f"Đã xác định ID quán: {res_id}")
    if st.button("🚀 Bắt đầu cào bình luận"):
        all_comments = []
        api_url = "https://gappapi.deliverynow.vn/api/v5/reply/get_replies"
        headers = {"x-foody-client-type": "1"}
        
        with st.spinner("Đang tải dữ liệu..."):
            for page in range(1, 6):
                params = {"restaurant_id": res_id, "page": str(page), "count": "10", "reply_type": "1"}
                try:
                    r = requests.get(api_url, headers=headers, params=params, timeout=5)
                    replies = r.json().get("reply_infos", [])
                    if not replies: break
                    for item in replies:
                        all_comments.append({
                            "Khách hàng": item.get("user", {}).get("display_name", "Ẩn danh"),
                            "Bình luận": item.get("message", ""),
                            "Số sao": item.get("rating", 5)
                        })
                except: break
        
        if all_comments:
            df = pd.DataFrame(all_comments)
            output = BytesIO()
            df.to_excel(output, index=False)
            st.download_button("📥 Tải File Excel", data=output.getvalue(), file_name=f"binh_luan_{res_id}.xlsx")
        else:
            st.warning("Không tìm thấy bình luận nào cho ID này.")