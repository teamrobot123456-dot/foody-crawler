import streamlit as st
import requests
import pandas as pd
import time
import re
from io import BytesIO

# Cấu hình giao diện
st.set_page_config(page_title="Công Cụ Cào Dữ Liệu", page_icon="🍜", layout="centered")

st.title("🍜 Siêu Công Cụ Cào Dữ Liệu Bình Luận")

def get_shopeefood_id_from_url(url):
    clean_url = url.strip().split("?")[0]
    # Bỏ hết các phần đuôi thừa thãi của Foody
    clean_url = re.sub(r'/(binh-luan|album|video|ban-do|thuc-don|uu-dai|thong-tin).*$', '', clean_url)
    slug = clean_url.strip("/").split("/")[-1]
    
    headers = {
        "x-foody-client-type": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # API tra cứu ID chuẩn
        api_url = f"https://gappapi.deliverynow.vn/api/delivery/get_detail?request_value={slug}&request_type=2"
        r = requests.get(api_url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            # Tìm ID trong kết quả
            reply = data.get("reply", {})
            restaurant_id = reply.get("delivery_id") or data.get("search_result", {}).get("delivery_id")
            return str(restaurant_id) if restaurant_id else None
    except:
        return None
    return None

input_data = st.text_input("Dán link quán tại đây:", placeholder="Ví dụ: https://www.foody.vn/ha-noi/banh-mi-sot-vang-dinh-ngang/binh-luan")

if st.button("🚀 Bắt đầu cào dữ liệu"):
    if not input_data:
        st.warning("Mẹ ơi, mẹ chưa dán link kìa!")
    else:
        with st.spinner("🔍 Đang giải mã link..."):
            res_id = get_shopeefood_id_from_url(input_data)
            
        if not res_id:
            st.error("Không tìm thấy ID. Mẹ thử dán link trang chủ của quán (không có /binh-luan ở cuối) xem sao nhé!")
        else:
            st.success(f"✅ Đã tìm thấy quán! Đang tải bình luận...")
            all_comments = []
            api_url = "https://gappapi.deliverynow.vn/api/v5/reply/get_replies"
            
            for page in range(1, 6): # Tải 5 trang đầu
                params = {"restaurant_id": res_id, "page": str(page), "count": "10", "reply_type": "1"}
                r = requests.get(api_url, headers={"x-foody-client-type": "1"}, params=params, timeout=5)
                if r.status_code == 200:
                    replies = r.json().get("reply_infos", [])
                    if not replies: break
                    for item in replies:
                        all_comments.append({
                            "Khách hàng": item.get("user", {}).get("display_name", "Ẩn danh"),
                            "Số sao": item.get("rating", 5),
                            "Bình luận": item.get("message", ""),
                            "Thời gian": time.strftime('%d-%m-%Y', time.localtime(item.get("create_time")))
                        })
                time.sleep(0.5)

            if all_comments:
                df = pd.DataFrame(all_comments)
                output = BytesIO()
                df.to_excel(output, index=False)
                st.download_button("📥 Tải File Excel Kết Quả", data=output.getvalue(), file_name=f"binh_luan_{res_id}.xlsx")
            else:
                st.warning("Quán này không có bình luận nào hoặc bị lỗi truy xuất!")