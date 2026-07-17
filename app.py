import streamlit as st
import requests
import pandas as pd
import time
from io import BytesIO

st.set_page_config(page_title="Siêu Cào Dữ Liệu", page_icon="🍜")
st.title("🍜 Siêu Công Cụ Cào Dữ Liệu")

def get_id_from_url(url):
    """Sử dụng API chuẩn của ShopeeFood để lấy ID từ Slug (tên quán trên link)"""
    # Lấy slug từ link (ví dụ: 'banh-mi-sot-vang-dinh-ngang')
    slug = url.strip("/").split("/")[-1].split("?")[0]
    
    # API này là 'cửa chính' để lấy thông tin quán
    api_url = f"https://gappapi.deliverynow.vn/api/delivery/get_detail?request_value={slug}&request_type=2"
    headers = {
        "x-foody-client-type": "1",
        "x-foody-api-version": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        r = requests.get(api_url, headers=headers, timeout=10)
        data = r.json()
        # Lấy ID từ cấu trúc JSON trả về
        if "search_result" in data:
            return str(data["search_result"].get("delivery_id"))
        elif "reply" in data:
            return str(data["reply"].get("delivery_id"))
    except:
        pass
    return None

input_data = st.text_input("Dán link quán vào đây (ShopeeFood/Foody):")

if input_data:
    with st.spinner("Đang kết nối tới máy chủ ShopeeFood..."):
        res_id = get_id_from_url(input_data)
        
    if res_id:
        st.success(f"Tìm thấy quán (ID: {res_id})! Đang cào bình luận...")
        
        # Cào dữ liệu
        all_comments = []
        api_comment_url = "https://gappapi.deliverynow.vn/api/v5/reply/get_replies"
        for page in range(1, 6): # Cào 5 trang đầu
            params = {"restaurant_id": res_id, "page": str(page), "count": "10", "reply_type": "1"}
            r = requests.get(api_comment_url, headers={"x-foody-client-type": "1"}, params=params, timeout=5)
            if r.status_code == 200:
                replies = r.json().get("reply_infos", [])
                if not replies: break
                for item in replies:
                    all_comments.append({
                        "Khách hàng": item.get("user", {}).get("display_name", "Ẩn danh"),
                        "Bình luận": item.get("message", ""),
                        "Số sao": item.get("rating", 5)
                    })
        
        if all_comments:
            df = pd.DataFrame(all_comments)
            output = BytesIO()
            df.to_excel(output, index=False)
            st.download_button("📥 Tải File Excel Kết Quả", data=output.getvalue(), file_name=f"binh_luan_{res_id}.xlsx")
        else:
            st.warning("Không tìm thấy bình luận nào cho quán này.")
    else:
        st.error("Không tìm thấy ID từ link này. Bạn thử kiểm tra lại link xem có đúng là trang quán không nhé!")