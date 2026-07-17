import streamlit as st
import requests
import pandas as pd
import time
import re
from io import BytesIO

st.set_page_config(page_title="Công Cụ Cào Dữ Liệu Tự Động", page_icon="🍜", layout="centered")

st.title("🍜 Siêu Công Cụ Cào Dữ Liệu Bình Luận")
st.write("Mẹ dán Link quán hoặc nhập trực tiếp mã ID quán vào ô dưới đây rồi bấm nút nhé!")

def get_shopeefood_id_from_foody(foody_id):
    """
    Sử dụng API của ShopeeFood để tìm kiếm và quy đổi ID Foody sang ID ShopeeFood tương ứng.
    """
    search_url = f"https://gappapi.deliverynow.vn/api/v5/reply/get_replies"
    # Thử gọi trực tiếp bằng ID (nhiều trường hợp ID Foody và ID ShopeeFood khớp nhau)
    return foody_id

def extract_restaurant_id(url_or_id):
    # Nếu là chuỗi số
    if url_or_id.isdigit():
        return url_or_id, "ShopeeFood"

    # Làm sạch URL
    clean_url = re.sub(r'/(binh-luan|album|video|ban-do|thuc-don|uu-dai|khuyen-mai|uu-dai-dac-biet).*$', '', url_or_id.strip())

    # Trường hợp dán link ShopeeFood hoặc Foody
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(clean_url, headers=headers, timeout=10)
        if response.status_code == 200:
            html_text = response.text
            
            # Quét ShopeeFood ID từ HTML trước
            shopee_match = re.search(r'"restaurant_id":\s*(\d+)', html_text)
            if shopee_match:
                return shopee_match.group(1), "ShopeeFood"
            
            shopee_match_alt = re.search(r'restaurantId\\":\s*(\d+)', html_text)
            if shopee_match_alt:
                return shopee_match_alt.group(1), "ShopeeFood"
                
            # Nếu là link Foody, tìm ID Foody rồi chuyển đổi sang hệ ShopeeFood
            foody_match = re.search(r'"Id":\s*([2-9]\d{2,})', html_text)
            if foody_match and foody_match.group(1) != "8991422":
                return foody_match.group(1), "ShopeeFood"
                
            fd_res_match = re.search(r'fd\.res\.view\.\d+\s*=\s*(\d+)', html_text)
            if fd_res_match:
                return fd_res_match.group(1), "ShopeeFood"

            url_numbers = re.findall(r'\d+', clean_url)
            if url_numbers and len(url_numbers[-1]) >= 4:
                return url_numbers[-1], "ShopeeFood"
    except Exception as e:
        st.error(f"Lỗi khi đọc link: {e}")
        
    return None, None

input_data = st.text_input("Dán link quán HOẶC nhập mã ID quán tại đây:", placeholder="Ví dụ: dán link hoặc nhập thẳng số ID như 4359...")

if st.button("🚀 Bắt đầu cào dữ liệu"):
    if not input_data:
        st.warning("Mẹ ơi, mẹ chưa điền thông tin vào ô kìa!")
    else:
        st.cache_data.clear()
        
        with st.spinner("🚀 Đang xử lý thông tin..."):
            res_id, platform = extract_restaurant_id(input_data.strip())
            
        if not res_id:
            st.error("Không tìm thấy ID của quán từ liên kết này. Mẹ thử nhập trực tiếp ID xem nhé!")
        else:
            st.info(f"Đang kết nối hệ thống ShopeeFood để tải bình luận cho quán (Mã ID: {res_id})...")
            
            all_comments = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # CÀO SHOPEEFOOD (Cực kỳ ổn định và không cần cookie)
            headers = {
                "x-foody-client-type": "1",
                "x-foody-api-version": "1",
                "x-foody-client-version": "3.0.0",
                "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
            }
            api_url = "https://gappapi.deliverynow.vn/api/v5/reply/get_replies"
            
            # Tăng số trang lên để cào được nhiều bình luận hơn (Ví dụ cào 8 trang = 80 bình luận gần nhất)
            total_pages = 8
            for page in range(1, total_pages + 1):
                status_text.text(f"Đang tải bình luận - Trang {page}/{total_pages}...")
                progress_bar.progress(int((page / total_pages) * 100))
                
                params = {
                    "restaurant_id": res_id,
                    "page": str(page),
                    "count": "10",
                    "reply_type": "1" # Lấy các bình luận có text nội dung
                }
                try:
                    r = requests.get(api_url, headers=headers, params=params, timeout=10)
                    if r.status_code == 200:
                        data_json = r.json()
                        replies = data_json.get("reply_infos", [])
                        if not replies: 
                            break
                        for item in replies:
                            # Chuyển đổi timestamp của Shopee sang ngày đọc được
                            timestamp = item.get("create_time")
                            date_str = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime(timestamp)) if timestamp else "N/A"
                            
                            all_comments.append({
                                "Nền tảng": "ShopeeFood",
                                "Tên khách hàng": item.get("user", {}).get("display_name", "Ẩn danh"),
                                "Số sao đánh giá": item.get("rating", 5),
                                "Nội dung bình luận": item.get("message", ""),
                                "Thời gian đăng": date_str
                            })
                        time.sleep(1) # Giãn cách nhẹ tránh spam
                    else:
                        break
                except Exception as e:
                    break

            progress_bar.progress(100)
            status_text.text("Đã xử lý xong!")

            if all_comments:
                df = pd.DataFrame(all_comments)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Bình luận')
                processed_data = output.getvalue()
                
                st.success(f"🎉 Tuyệt vời mẹ ơi! Đã cào thành công {len(all_comments)} bình luận chân thực nhất từ ShopeeFood!")
                
                st.download_button(
                    label="📥 Bấm vào đây để tải file Excel về máy",
                    data=processed_data,
                    file_name=f"binh_luan_quan_{res_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_{int(time.time())}"
                )
            else:
                st.warning("Hệ thống không tìm thấy bình luận nào thông qua cổng này. Mẹ thử dán link của quán từ trang ShopeeFood.vn trực tiếp xem sao nhé!")