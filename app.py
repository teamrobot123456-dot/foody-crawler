import streamlit as st
import requests
import pandas as pd
import time
import re
from io import BytesIO

st.set_page_config(page_title="Công Cụ Cào Dữ Liệu Tự Động", page_icon="🍜", layout="centered")

st.title("🍜 Siêu Công Cụ Cào Dữ Liệu Bình Luận")
st.write("Mẹ dán Link quán hoặc nhập trực tiếp mã ID quán vào ô dưới đây rồi bấm nút nhé!")

# Hàm tự động quét tìm ID quán từ HTML của đường link
def extract_restaurant_id(url_or_id):
    # Nếu người dùng nhập thẳng một chuỗi số (ID quán)
    if url_or_id.isdigit():
        if len(url_or_id) < 8:
            return url_or_id, "Foody"
        else:
            return url_or_id, "ShopeeFood"

    # Làm sạch URL: Nếu link có đuôi /binh-luan, /khuyen-mai... thì cắt bỏ đi để lấy link gốc của quán
    clean_url = re.sub(r'/(binh-luan|album|video|ban-do|thuc-don|uu-dai|khuyen-mai|uu-dai-dac-biet).*$', '', url_or_id.strip())

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(clean_url, headers=headers, timeout=10)
        if response.status_code == 200:
            html_text = response.text
            
            # 1. Tìm ID kiểu Foody trong thẻ meta hoặc script
            # Tìm ID trong fd.res.view hoặc các biến cấu trúc của Foody
            foody_match = re.search(r'"Id":\s*([2-9]\d{2,})', html_text)
            if foody_match:
                # Kiểm tra tránh lấy nhầm ID người dùng hoặc ID ảo quá nhỏ
                val = foody_match.group(1)
                if val != "8991422": # Loại trừ ID trang bình luận chung
                    return val, "Foody"
            
            # Tìm cua phòng hờ Foody bằng regex quét từ javascript gốc của trang
            fd_res_match = re.search(r'fd\.res\.view\.\d+\s*=\s*(\d+)', html_text)
            if fd_res_match:
                return fd_res_match.group(1), "Foody"

            # Quét số cuối cùng trong URL làm phương án dự phòng (Foody cũ thường để ID ở cuối link)
            url_numbers = re.findall(r'\d+', clean_url)
            if url_numbers and len(url_numbers[-1]) >= 4:
                return url_numbers[-1], "Foody"
            
            # 2. Quét tìm ID kiểu ShopeeFood
            shopee_match = re.search(r'"restaurant_id":\s*(\d+)', html_text)
            if shopee_match:
                return shopee_match.group(1), "ShopeeFood"
            
            shopee_match_alt = re.search(r'restaurantId\\":\s*(\d+)', html_text)
            if shopee_match_alt:
                return shopee_match_alt.group(1), "ShopeeFood"
    except Exception as e:
        st.error(f"Không thể kết nối tới đường link để lấy ID tự động: {e}")
    return None, None

# Ô nhập đa năng cho mẹ
input_data = st.text_input("Dán link quán HOẶC nhập mã ID quán tại đây:", placeholder="Ví dụ: dán link hoặc nhập thẳng số ID như 16787...")

if st.button("🚀 Bắt đầu cào dữ liệu"):
    if not input_data:
        st.warning("Mẹ ơi, mẹ chưa điền thông tin vào ô kìa!")
    else:
        st.cache_data.clear()
        
        with st.spinner("🚀 Đang xử lý thông tin..."):
            res_id, platform = extract_restaurant_id(input_data.strip())
            
        # Phòng hờ nếu quét ra ID không hợp lệ
        if not res_id or res_id in ["1", "8991422"]:
            st.error("Không thể lấy ID tự động từ link này. Mẹ vui lòng nhập trực tiếp mã ID của quán (ví dụ: 4359) vào ô trên nhé!")
        else:
            st.info(f"Đang tiến hành cào ID quán: {res_id} (Hệ thống: {platform})")
            
            all_comments = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # CÀO FOODY
            if platform == "Foody":
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                cookie = "flg=vn; __ondemand_sessionid=vn23gsnjnutvfpyaj1gv2bcd; floc=218; gcat=food;"
                headers = {
                    "user-agent": user_agent,
                    "cookie": cookie,
                    "accept": "application/json, text/javascript, */*; q=0.01",
                    "x-requested-with": "XMLHttpRequest"
                }
                api_url = "https://www.foody.vn/__get/Review/ResLoadMore"
                last_id = ""
                
                for page in range(1, 6):
                    status_text.text(f"Đang cào Foody - Trang {page}...")
                    progress_bar.progress(page * 20)
                    params = {
                        "t": str(int(time.time() * 1000)),
                        "ResId": res_id,
                        "LastId": last_id,
                        "Count": "10",
                        "Type": "1",
                        "isLatest": "true"
                    }
                    try:
                        r = requests.get(api_url, headers=headers, params=params, timeout=10)
                        if r.status_code == 200:
                            items = r.json().get("Items", [])
                            if not items: break
                            for item in items:
                                all_comments.append({
                                    "Nền tảng": "Foody",
                                    "Tên người dùng": item.get("Owner", {}).get("DisplayName"),
                                    "Số điểm": item.get("AverageRating"),
                                    "Nội dung bình luận": item.get("Description"),
                                    "Ngày đăng": item.get("CreatedDate")
                                })
                            last_id = str(items[-1].get("Id"))
                            time.sleep(1)
                        else:
                            break
                    except:
                        break
            
            # CÀO SHOPEEFOOD
            elif platform == "ShopeeFood":
                headers = {
                    "x-foody-client-type": "1",
                    "x-foody-api-version": "1",
                    "x-foody-client-version": "3.0.0",
                    "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
                }
                api_url = "https://gappapi.deliverynow.vn/api/v5/reply/get_replies"
                
                for page in range(1, 6):
                    status_text.text(f"Đang cào ShopeeFood - Trang {page}...")
                    progress_bar.progress(page * 20)
                    params = {
                        "restaurant_id": res_id,
                        "page": str(page),
                        "count": "10",
                        "reply_type": "1"
                    }
                    try:
                        r = requests.get(api_url, headers=headers, params=params, timeout=10)
                        if r.status_code == 200:
                            replies = r.json().get("reply_infos", [])
                            if not replies: break
                            for item in replies:
                                all_comments.append({
                                    "Nền tảng": "ShopeeFood",
                                    "Tên người dùng": item.get("user", {}).get("display_name"),
                                    "Số điểm": item.get("rating"),
                                    "Nội dung bình luận": item.get("message"),
                                    "Ngày đăng": item.get("create_time")
                                })
                            time.sleep(1)
                        else:
                            break
                    except:
                        break

            progress_bar.progress(100)
            status_text.text("Đã hoàn thành!")

            if all_comments:
                df = pd.DataFrame(all_comments)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Comments')
                processed_data = output.getvalue()
                
                st.success(f"🎉 Xuất sắc mẹ ơi! Đã cào thành công {len(all_comments)} bình luận của quán!")
                
                st.download_button(
                    label="📥 Bấm vào đây để tải file Excel về máy",
                    data=processed_data,
                    file_name=f"binh_luan_{platform}_{res_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_{int(time.time())}"
                )
            else:
                st.warning("Không tìm thấy bình luận nào cho quán này.")