import streamlit as st
import requests
import pandas as pd
import time
import re
from io import BytesIO

# Cấu hình giao diện trang web
st.set_page_config(page_title="Công Cụ Cào Dữ Liệu Tự Động", page_icon="🍜", layout="centered")

st.title("🍜 Siêu Công Cụ Cào Dữ Liệu Bình Luận")
st.write("Mẹ dán Link quán hoặc nhập trực tiếp mã ID quán vào ô dưới đây rồi bấm nút nhé!")

def extract_restaurant_id(url_or_id):
    """
    Hàm bóc tách ID quán thông minh:
    - Nếu nhập ID số: Giữ nguyên.
    - Nếu dán link: Cắt bỏ rác, lấy alias tên quán và gọi API ShopeeFood để tìm ID chuẩn 100%.
    """
    # 1. Nếu người dùng nhập thẳng số ID
    if url_or_id.isdigit():
        return url_or_id, "ShopeeFood"

    clean_url = url_or_id.strip()
    
    # 2. Làm sạch link: Cắt bỏ các hậu tố như /binh-luan, /thuc-don...
    clean_url = re.sub(r'/(binh-luan|album|video|ban-do|thuc-don|uu-dai|khuyen-mai|uu-dai-dac-biet).*$', '', clean_url)

    # 3. Xử lý link Foody (Ví dụ: https://www.foody.vn/ha-noi/banh-mi-sot-vang-dinh-ngang)
    # Trích xuất phần "alias" tên quán ở cuối đường dẫn
    match_alias = re.search(r'foody\.vn/[^/]+/([^/]+)', clean_url)
    if match_alias:
        alias = match_alias.group(1)
        
        # Gọi API Search của ShopeeFood để truy quét ID thật dựa trên tên quán (alias)
        search_api = "https://gappapi.deliverynow.vn/api/v5/delivery/search_restaurant"
        headers = {
            "x-foody-client-type": "1",
            "x-foody-api-version": "1",
            "x-foody-client-version": "3.0.0",
            "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
        }
        # Đổi dấu gạch ngang '-' thành khoảng trắng để Shopee tìm kiếm chuẩn hơn
        search_keyword = alias.replace('-', ' ')
        params = {
            "keyword": search_keyword,
            "limit": "5"
        }
        try:
            r = requests.get(search_api, headers=headers, params=params, timeout=10)
            if r.status_code == 200:
                restaurants = r.json().get("reply", {}).get("restaurants", [])
                if restaurants:
                    # Lấy ID của quán đầu tiên (độ khớp cao nhất)
                    shopee_id = restaurants[0].get("restaurant_id")
                    if shopee_id:
                        return str(shopee_id), "ShopeeFood"
        except Exception:
            pass

    # 4. Xử lý link ShopeeFood trực tiếp (nếu mẹ dán link shopeefood.vn)
    shopee_url_match = re.search(r'shopeefood\.vn/[^/]+/([^/]+)$', clean_url)
    if shopee_url_match:
        alias = shopee_url_match.group(1)
        id_match = re.findall(r'\d+', alias)
        if id_match:
            return id_match[-1], "ShopeeFood"

    # 5. Phương án dự phòng cuối: quét mọi chuỗi số xuất hiện trong link (loại trừ các số ID rác đã biết)
    url_numbers = re.findall(r'\d+', clean_url)
    if url_numbers:
        valid_numbers = [num for num in url_numbers if num not in ["54270", "8991422"] and len(num) >= 4]
        if valid_numbers:
            return valid_numbers[-1], "ShopeeFood"
        
    return None, None

# Ô nhập liệu thân thiện cho mẹ
input_data = st.text_input("Dán link quán HOẶC nhập mã ID quán tại đây:", placeholder="Ví dụ: dán link hoặc nhập thẳng số ID như 4359...")

if st.button("🚀 Bắt đầu cào dữ liệu"):
    if not input_data:
        st.warning("Mẹ ơi, mẹ chưa điền thông tin vào ô kìa!")
    else:
        st.cache_data.clear()
        
        with st.spinner("🚀 Đang xử lý thông tin..."):
            res_id, platform = extract_restaurant_id(input_data.strip())
            
        if not res_id:
            st.error("Không tìm thấy ID của quán từ liên kết này. Mẹ thử nhập trực tiếp mã ID (ví dụ: 4359) xem nhé!")
        else:
            st.info(f"Đang kết nối hệ thống ShopeeFood để tải bình luận cho quán (Mã ID: {res_id})...")
            
            all_comments = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # API ShopeeFood (ổn định, bảo mật thoáng, dùng chung database bình luận với Foody)
            headers = {
                "x-foody-client-type": "1",
                "x-foody-api-version": "1",
                "x-foody-client-version": "3.0.0",
                "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
            }
            api_url = "https://gappapi.deliverynow.vn/api/v5/reply/get_replies"
            
            # Cào 8 trang gần nhất (khoảng 80 bình luận có nội dung)
            total_pages = 8
            for page in range(1, total_pages + 1):
                status_text.text(f"Đang tải bình luận - Trang {page}/{total_pages}...")
                progress_bar.progress(int((page / total_pages) * 100))
                
                params = {
                    "restaurant_id": res_id,
                    "page": str(page),
                    "count": "10",
                    "reply_type": "1"  # Chỉ lấy những bình luận có chữ viết kèm theo
                }
                try:
                    r = requests.get(api_url, headers=headers, params=params, timeout=10)
                    if r.status_code == 200:
                        data_json = r.json()
                        replies = data_json.get("reply_infos", [])
                        if not replies: 
                            break
                        
                        for item in replies:
                            timestamp = item.get("create_time")
                            date_str = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime(timestamp)) if timestamp else "N/A"
                            
                            all_comments.append({
                                "Nền tảng": "ShopeeFood",
                                "Tên khách hàng": item.get("user", {}).get("display_name", "Ẩn danh"),
                                "Số sao đánh giá": item.get("rating", 5),
                                "Nội dung bình luận": item.get("message", ""),
                                "Thời gian đăng": date_str
                            })
                        time.sleep(1)  # Giãn cách nhẹ tránh bị hệ thống quét spam
                    else:
                        break
                except Exception:
                    break

            progress_bar.progress(100)
            status_text.text("Đã xử lý xong!")

            if all_comments:
                df = pd.DataFrame(all_comments)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Bình luận')
                processed_data = output.getvalue()
                
                st.success(f"🎉 Tuyệt vời mẹ ơi! Đã cào thành công {len(all_comments)} bình luận chân thực nhất!")
                
                st.download_button(
                    label="📥 Bấm vào đây để tải file Excel về máy",
                    data=processed_data,
                    file_name=f"binh_luan_quan_{res_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_{int(time.time())}"
                )
            else:
                st.warning("Hệ thống không tìm thấy bình luận nào thông qua cổng này. Mẹ thử dán link của quán trực tiếp từ trang ShopeeFood.vn xem sao nhé!")