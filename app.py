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
    Hàm bóc tách ID quán an toàn, không bao giờ gây sập app.
    """
    try:
        if url_or_id.isdigit():
            return url_or_id, "ShopeeFood"

        clean_url = url_or_id.strip()
        clean_url = re.sub(r'/(binh-luan|album|video|ban-do|thuc-don|uu-dai|khuyen-mai|uu-dai-dac-biet).*$', '', clean_url)

        # Xử lý link Foody bằng cách tìm kiếm trên ShopeeFood
        match_alias = re.search(r'foody\.vn/[^/]+/([^/]+)', clean_url)
        if match_alias:
            alias = match_alias.group(1)
            search_api = "https://gappapi.deliverynow.vn/api/v5/delivery/search_restaurant"
            headers = {
                "x-foody-client-type": "1",
                "x-foody-api-version": "1",
                "x-foody-client-version": "3.0.0",
                "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
            }
            search_keyword = alias.replace('-', ' ')
            params = {"keyword": search_keyword, "limit": "5"}
            
            r = requests.get(search_api, headers=headers, params=params, timeout=10)
            if r.status_code == 200:
                restaurants = r.json().get("reply", {}).get("restaurants", [])
                if restaurants:
                    shopee_id = restaurants[0].get("restaurant_id")
                    if shopee_id:
                        return str(shopee_id), "ShopeeFood"
    except Exception as e:
        st.warning(f"Lưu ý nhẹ: Có chút lỗi khi tự nhận diện link ({str(e)}).")
        
    # Phương án dự phòng: Tìm chuỗi số cuối cùng trong link
    try:
        url_numbers = re.findall(r'\d+', url_or_id)
        if url_numbers:
            valid_numbers = [num for num in url_numbers if num not in ["54270", "8991422"] and len(num) >= 4]
            if valid_numbers:
                return valid_numbers[-1], "ShopeeFood"
    except Exception:
        pass

    return None, None

# Ô nhập liệu
input_data = st.text_input("Dán link quán HOẶC nhập mã ID quán tại đây:", placeholder="Ví dụ: 4359...")

if st.button("🚀 Bắt đầu cào dữ liệu"):
    if not input_data:
        st.warning("Mẹ ơi, mẹ chưa điền thông tin vào ô kìa!")
    else:
        st.cache_data.clear()
        
        with st.spinner("🚀 Đang xử lý thông tin..."):
            res_id, platform = extract_restaurant_id(input_data.strip())
            
        if not res_id:
            st.error("Không tìm thấy ID của quán từ liên kết này. Mẹ thử nhập trực tiếp mã ID (ví dụ: 4359) vào ô trên nhé!")
        else:
            st.info(f"Đang kết nối hệ thống ShopeeFood để tải bình luận cho quán (Mã ID: {res_id})...")
            
            all_comments = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # API ShopeeFood
            headers = {
                "x-foody-client-type": "1",
                "x-foody-api-version": "1",
                "x-foody-client-version": "3.0.0",
                "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
            }
            api_url = "https://gappapi.deliverynow.vn/api/v5/reply/get_replies"
            
            total_pages = 8
            for page in range(1, total_pages + 1):
                status_text.text(f"Đang tải bình luận - Trang {page}/{total_pages}...")
                progress_bar.progress(int((page / total_pages) * 100))
                
                params = {
                    "restaurant_id": res_id,
                    "page": str(page),
                    "count": "10",
                    "reply_type": "1"
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
                        time.sleep(1)
                    else:
                        break
                except Exception:
                    break

            progress_bar.progress(100)
            status_text.text("Đã xử lý xong!")

            if all_comments:
                df = pd.DataFrame(all_comments)
                
                # CƠ CHẾ XUẤT FILE AN TOÀN TUYỆT ĐỐI
                try:
                    # Thử xuất file Excel (.xlsx) trước
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Bình luận')
                    processed_data = output.getvalue()
                    file_name = f"binh_luan_quan_{res_id}.xlsx"
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                except Exception:
                    # Nếu lỗi (thiếu thư viện openpyxl), tự động chuyển sang xuất file CSV (.csv)
                    # File CSV vẫn mở bằng Excel bình thường cực kỳ ngon lành!
                    csv_data = df.to_csv(index=False, encoding='utf-8-sig')
                    processed_data = csv_data.encode('utf-8-sig')
                    file_name = f"binh_luan_quan_{res_id}.csv"
                    mime_type = "text/csv"
                
                st.success(f"🎉 Tuyệt vời mẹ ơi! Đã cào thành công {len(all_comments)} bình luận!")
                
                st.download_button(
                    label="📥 Bấm vào đây để tải file kết quả về máy",
                    data=processed_data,
                    file_name=file_name,
                    mime=mime_type,
                    key=f"download_{int(time.time())}"
                )
            else:
                st.warning("Hệ thống không tìm thấy bình luận nào. Mẹ thử dán link khác hoặc nhập thẳng ID xem nhé!")