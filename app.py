import streamlit as st
import requests
import pandas as pd
import time
import re
from io import BytesIO

st.set_page_config(page_title="Công Cụ Cào Dữ Liệu Tự Động", page_icon="🍜", layout="centered")

st.title("🍜 Siêu Công Cụ Cào Dữ Liệu Bình Luận")
st.write("Mẹ dán Link quán hoặc nhập trực tiếp mã ID quán vào ô dưới đây rồi bấm nút nhé!")

def extract_restaurant_id(url_or_id):
    if url_or_id.isdigit():
        if len(url_or_id) < 8:
            return url_or_id, "Foody"
        else:
            return url_or_id, "ShopeeFood"

    clean_url = re.sub(r'/(binh-luan|album|video|ban-do|thuc-don|uu-dai|khuyen-mai|uu-dai-dac-biet).*$', '', url_or_id.strip())

    match_alias = re.search(r'foody\.vn/[^/]+/([^/]+)', clean_url)
    if match_alias:
        alias = match_alias.group(1)
        search_api = f"https://www.foody.vn/__get/Restaurant/Detail?url={alias}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.foody.vn/"
        }
        try:
            r = requests.get(search_api, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                res_id = data.get("Id") or data.get("RestaurantId")
                if res_id:
                    return str(res_id), "Foody"
        except:
            pass
            
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
            st.error("Không thể lấy ID tự động từ link này. Mẹ vui lòng nhập trực tiếp mã ID của quán (ví dụ: 4359) vào ô trên nhé!")
        else:
            st.info(f"Đang tiến hành cào ID quán: {res_id} (Hệ thống: {platform})")
            
            all_comments = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # CÀO FOODY (ĐÃ TỐI ƯU HEADER SẠCH)
            if platform == "Foody":
                # Dùng các thông số header cơ bản, không nhồi nhét cookie cũ tránh bị nghi ngờ
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"https://www.foody.vn/nhahang/detail?id={res_id}"
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
                            # Thử bóc tách JSON an toàn
                            res_json = r.json()
                            items = res_json.get("Items", []) if isinstance(res_json, dict) else []
                            
                            if not items: 
                                break
                            for item in items:
                                all_comments.append({
                                    "Nền tảng": "Foody",
                                    "Tên người dùng": item.get("Owner", {}).get("DisplayName"),
                                    "Số điểm": item.get("AverageRating"),
                                    "Nội dung bình luận": item.get("Description"),
                                    "Ngày đăng": item.get("CreatedDate")
                                })
                            last_id = str(items[-1].get("Id"))
                            time.sleep(1.5)
                        else:
                            st.error(f"Phía Foody từ chối kết nối (Mã lỗi: {r.status_code}).")
                            break
                    except Exception as e:
                        st.error(f"Lỗi khi tải trang {page}: {str(e)}")
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
                            time.sleep(1.5)
                        else:
                            st.error(f"Phía ShopeeFood từ chối kết nối (Mã lỗi: {r.status_code}).")
                            break
                    except Exception as e:
                        st.error(f"Lỗi khi tải trang {page}: {str(e)}")
                        break

            progress_bar.progress(100)
            status_text.text("Đã xử lý xong!")

            if all_comments:
                df = pd.DataFrame(all_comments)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Comments')
                processed_data = output.getvalue()
                
                st.success(f"🎉 Xuất sắc mẹ ơi! Đã cào thành công {len(all_comments)} bình luận!")
                
                st.download_button(
                    label="📥 Bấm vào đây để tải file Excel về máy",
                    data=processed_data,
                    file_name=f"binh_luan_{platform}_{res_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_{int(time.time())}"
                )
            else:
                st.warning("Không tìm thấy bình luận nào cho quán này. Mẹ kiểm tra lại xem quán có bình luận nào hiển thị công khai không nhé!")