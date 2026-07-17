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

def get_shopeefood_id_from_url(url):
    """
    Hàm tự động truy cập vào trang web ShopeeFood/Foody để bóc tách ID ẩn trong HTML
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    clean_url = url.strip()
    
    # 1. Nếu người dùng nhập thẳng số ID thì dùng luôn
    if clean_url.isdigit():
        return clean_url

    try:
        # 2. Nếu là link Foody, thử chuyển hướng hoặc tìm cách quét link ShopeeFood tương ứng
        if "foody.vn" in clean_url:
            # Cắt bỏ phần /binh-luan ở cuối nếu có
            clean_url = re.sub(r'/(binh-luan|album|video|ban-do|thuc-don|uu-dai).*$', '', clean_url)
            # Thử gọi lên Foody để lấy HTML và tìm ID quán hoặc link ShopeeFood đi kèm
            r = requests.get(clean_url, headers=headers, timeout=10)
            if r.status_code == 200:
                # Tìm ID của Foody trong HTML
                foody_id_match = re.search(r'"RestaurantId"\s*:\s*(\d+)', r.text) or re.search(r'RestaurantID=(\d+)', r.text)
                if foody_id_match:
                    return foody_id_match.group(1)
                
                # Hoặc tìm link ShopeeFood chứa trong nút "Đặt giao hàng"
                shopee_link_match = re.search(r'href="([^"]*shopeefood\.vn/[^"]*)"', r.text)
                if shopee_link_match:
                    clean_url = shopee_link_match.group(1)

        # 3. Truy cập thẳng vào link ShopeeFood để bới ID ẩn trong HTML
        if "shopeefood.vn" in clean_url:
            r = requests.get(clean_url, headers=headers, timeout=10)
            if r.status_code == 200:
                html_content = r.text
                
                # Tìm kiếm ID trong các thẻ cấu hình ẩn của ShopeeFood (Thường nằm trong Redux State hoặc Meta tags)
                patterns = [
                    r'"restaurant_id"\s*:\s*(\d+)',
                    r'"restaurantId"\s*:\s*(\d+)',
                    r'"delivery_id"\s*:\s*(\d+)',
                    r'"id"\s*:\s*(\d+)',
                    r'restaurant/(\d+)'
                ]
                for pattern in patterns:
                    match = re.search(pattern, html_content)
                    if match:
                        return match.group(1)
    except Exception as e:
        st.warning(f"Lưu ý: Hệ thống gặp chút gián đoạn khi quét tự động ({str(e)})")
        
    # Phương án dự phòng cuối cùng: quét mọi chuỗi số xuất hiện trong link
    numbers = re.findall(r'\d+', clean_url)
    if numbers:
        valid_numbers = [num for num in numbers if num not in ["54270", "8991422"] and len(num) >= 4]
        if valid_numbers:
            return valid_numbers[-1]
            
    return None

# Ô nhập liệu cực kỳ đơn giản cho mẹ
input_data = st.text_input("Dán link quán tại đây:", placeholder="Ví dụ: https://shopeefood.vn/ha-noi/bun-cha-obama-nguyen-thi-dinh")

if st.button("🚀 Bắt đầu cào dữ liệu"):
    if not input_data:
        st.warning("Mẹ ơi, mẹ chưa dán link vào kìa!")
    else:
        st.cache_data.clear()
        
        with st.spinner("🔍 Đang tự động phân tích và lấy ID quán ẩn dưới nền..."):
            res_id = get_shopeefood_id_from_url(input_data)
            
        if not res_id:
            st.error("Không thể tự động tìm thấy ID của quán này. Mẹ kiểm tra lại link xem có đúng không nhé!")
        else:
            st.info(f"🎉 Đã tìm thấy ID quán: {res_id}! Đang tiến hành tải bình luận...")
            
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