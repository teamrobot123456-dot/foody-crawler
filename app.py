import streamlit as st
import requests
import pandas as pd
import time
import re
from io import BytesIO

# Cấu hình giao diện
st.set_page_config(page_title="Công Cụ Cào Dữ Liệu", page_icon="🍜", layout="centered")

st.title("🍜 Siêu Công Cụ Cào Dữ Liệu Bình Luận")
st.write("Dành riêng cho mẹ cào dữ liệu ShopeeFood/Foody nhanh chóng!")

# Bảng hướng dẫn mẹ lấy ID cực kỳ dễ hiểu
with st.expander("💡 MẸ ƠI, BẤM VÀO ĐÂY XEM CÁCH LẤY MÃ ID QUÁN NHÉ!", expanded=True):
    st.markdown("""
    Vì hệ thống bảo mật chặn link trực tiếp, mẹ chỉ cần lấy **Mã ID (dạng số)** của quán theo 2 cách siêu dễ sau:
    
    1. **Lấy từ link ShopeeFood (Nhanh nhất):**
       * Mẹ tìm quán trên ShopeeFood, link quán sẽ có dạng: `shopeefood.vn/ha-noi/hoang-beo-pham-ngoc-thach-1000034567`
       * Mẹ chỉ cần copy dãy số ở cuối cùng: **`1000034567`** dán vào ô bên dưới nhé!
    
    2. **Lấy từ link Foody:**
       * Khi mẹ mở link Foody của quán, mẹ tìm nút màu đỏ **"Đặt giao hàng"** hoặc **"Đặt bàn"**.
       * Mã ID chính là dãy số đi kèm với nút đó.
    """)

def extract_id_from_input(user_input):
    """
    Trích xuất ID chuẩn: lấy chuỗi số cuối cùng từ link hoặc giữ nguyên nếu nhập số.
    """
    val = user_input.strip()
    if val.isdigit():
        return val
    
    # Nếu dán cả link, tự lọc ra chuỗi số cuối cùng (thường là ID quán trên ShopeeFood)
    numbers = re.findall(r'\d+', val)
    if numbers:
        # Bỏ qua các số ID rác của trang danh mục Foody
        valid_numbers = [n for n in numbers if n not in ["54270", "8991422"] and len(n) >= 4]
        if valid_numbers:
            return valid_numbers[-1]
    return None

# Ô nhập liệu
input_data = st.text_input("Mẹ nhập mã ID quán (hoặc link quán chứa ID số ở cuối) vào đây:", placeholder="Ví dụ: 4359 hoặc 1000034567...")

if st.button("🚀 Bắt đầu cào dữ liệu"):
    if not input_data:
        st.warning("Mẹ ơi, mẹ chưa điền thông tin vào ô kìa!")
    else:
        st.cache_data.clear()
        res_id = extract_id_from_input(input_data)
        
        if not res_id:
            st.error("Không nhận diện được ID số. Mẹ vui lòng nhập đúng dãy số ID của quán nhé!")
        else:
            st.info(f"Đang kết nối hệ thống để tải bình luận cho quán (Mã ID: {res_id})...")
            
            all_comments = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # API ShopeeFood gọi trực tiếp bằng ID (Không bao giờ lỗi)
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
                
                # Xuất file an toàn
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
                st.warning("Không tìm thấy bình luận nào cho ID này. Mẹ kiểm tra lại xem có nhập nhầm số ID của quán khác không nhé!")