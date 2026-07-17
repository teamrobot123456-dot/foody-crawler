import streamlit as st
import requests
import pandas as pd
import time
import re
from io import BytesIO

# Cấu hình giao diện
st.set_page_config(page_title="Công Cụ Cào Dữ Liệu", page_icon="🍜", layout="centered")

st.title("🍜 Siêu Công Cụ Cào Dữ Liệu Bình Luận")
st.write("Mẹ chỉ cần dán link quán (ShopeeFood hoặc Foody) vào ô dưới đây rồi bấm nút nhé!")

def find_key_recursive(data, target_key):
    """
    Hàm tìm kiếm sâu trong JSON để lục tìm ID của quán
    """
    if isinstance(data, dict):
        if target_key in data:
            return data[target_key]
        for v in data.values():
            res = find_key_recursive(v, target_key)
            if res is not None:
                return res
    elif isinstance(data, list):
        for item in data:
            res = find_key_recursive(item, target_key)
            if res is not None:
                return res
    return None

def get_shopeefood_id_from_url(url):
    """
    Giải mã link Foody/ShopeeFood thành ID chuẩn bằng API chính thức
    """
    headers = {
        "x-foody-client-type": "1",
        "x-foody-api-version": "1",
        "x-foody-client-version": "3.0.0",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    clean_url = url.strip()
    
    # 1. Nếu người dùng nhập thẳng số ID thì dùng luôn
    if clean_url.isdigit():
        return clean_url

    # 2. Xử lý cắt chuỗi để lấy tên không dấu của quán (Slug)
    # Loại bỏ các tham số rác đằng sau dấu chấm hỏi (?) nếu có
    clean_url = clean_url.split("?")[0].strip("/")
    # Loại bỏ các đuôi phụ của Foody như /binh-luan, /thuc-don...
    clean_url = re.sub(r'/(binh-luan|album|video|ban-do|thuc-don|uu-dai).*$', '', clean_url)
    
    # Lấy phần chữ cuối cùng trong link làm slug
    slug = clean_url.split("/")[-1]
    
    if not slug:
        return None

    try:
        # Gọi API ẩn của ShopeeFood để tra cứu chi tiết quán bằng tên không dấu (Slug)
        api_resolve_url = f"https://gappapi.deliverynow.vn/api/delivery/get_detail?request_value={slug}&request_type=2"
        r = requests.get(api_resolve_url, headers=headers, timeout=10)
        
        if r.status_code == 200:
            json_data = r.json()
            # Lục lọi trong kết quả trả về để tìm restaurant_id chuẩn của ShopeeFood
            restaurant_id = find_key_recursive(json_data, "restaurant_id")
            if restaurant_id:
                return str(restaurant_id)
    except Exception as e:
        st.warning(f"Đang thử phương án dự phòng do hệ thống bận...")

    # Phương án dự phòng cuối cùng: Tìm chuỗi số cuối cùng có trong link dán vào
    numbers = re.findall(r'\d+', clean_url)
    if numbers:
        valid_numbers = [num for num in numbers if num not in ["54270", "8991422"] and len(num) >= 4]
        if valid_numbers:
            return valid_numbers[-1]
            
    return None

# Giao diện chính cho mẹ sử dụng
input_data = st.text_input("Dán link quán tại đây:", placeholder="Ví dụ: https://www.foody.vn/ha-noi/banh-mi-sot-vang-dinh-ngang")

if st.button("🚀 Bắt đầu cào dữ liệu"):
    if not input_data:
        st.warning("Mẹ ơi, mẹ chưa dán link vào kìa!")
    else:
        st.cache_data.clear()
        
        with st.spinner("🔍 Hệ thống đang tự động phân tích và lấy ID quán ẩn..."):
            res_id = get_shopeefood_id_from_url(input_data)
            
        if not res_id:
            st.error("Không thể tự động tìm thấy ID của quán này. Mẹ kiểm tra lại link xem có đúng không nhé!")
        else:
            st.info(f"🎉 Đã kết nối thành công với quán (ID ShopeeFood: {res_id})! Đang tiến hành tải bình luận...")
            
            all_comments = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
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
                        time.sleep(0.8)
                    else:
                        break
                except Exception:
                    break

            progress_bar.progress(100)
            status_text.text("Đã xử lý xong!")

            if all_comments:
                df = pd.DataFrame(all_comments)
                
                try:
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Bình luận')
                    processed_data = output.getvalue()
                    file_name = f"binh_luan_quan_{res_id}.xlsx"
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                except Exception:
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
                st.warning("Hệ thống không tìm thấy bình luận nào cho quán này. Mẹ thử dán link khác xem nhé!")