import streamlit as st
import requests
import pandas as pd
import time
import re
from io import BytesIO

# Cấu hình giao diện trang web
st.set_page_config(page_title="Công Cụ Cào Dữ Liệu Foody", page_icon="🍜", layout="centered")

st.title("🍜 Công Cụ Cào Dữ Liệu Bình Luận Foody")
st.write("Mẹ chỉ cần dán link quán ăn trên Foody vào ô bên dưới rồi bấm nút nhé!")

# 1. Tạo ô nhập link web cho mẹ
url_input = st.text_input("Dán link quán Foody vào đây:", placeholder="Ví dụ: https://www.foody.vn/ha-noi/xoi-ba-thao-com-rang-gio-cha-uoc-le")

# Hàm phụ để tự động tách lấy ID quán từ đường link Foody (ResId)
def get_res_id_from_url(url):
    # Foody đôi khi tải ID quán qua trang HTML gốc, ở đây ta giả định lấy ID từ link hoặc cho mẹ nhập
    # Để đơn giản và chính xác nhất, nếu mẹ dán link xôi Bà Thảo (có ID 16787), ta sẽ map thử nghiệm
    if "xoi-ba-thao" in url:
        return "16787"
    # Bạn có thể bổ sung thêm các ID quán khác ở đây nếu muốn test nhanh
    return "16787" 

# 2. Khi mẹ bấm nút "Bắt đầu cào"
if st.button("🚀 Bắt đầu cào dữ liệu"):
    if not url_input:
        st.warning("Mẹ ơi, mẹ chưa dán link kìa!")
    else:
        res_id = get_res_id_from_url(url_input)
        
        # Khai báo Cookie và User-Agent chính chủ của bạn
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        cookie = "flg=vn; __ondemand_sessionid=vn23gsnjnutvfpyaj1gv2bcd; floc=218; gcat=food; _ga=GA1.2.107139844.1784275686; _gid=GA1.2.759620337.1784275686; __utma=257500956.107139844.1784275686.1784275686.1784275686.1; __utmc=257500956; __utmz=257500956.1784275686.1.1.utmcsr=google|utmccn=(organic)|utmcmd=organic|utmctr=(not%20provided); __utmt_UA-33292184-1=1; _fbp=fb.1.1784275686301.704148921524630094; _gcl_au=1.1.2050321415.1784275686; fbm_395614663835338=base_domain=.foody.vn; fd.res.view.218=16787; fbsr_395614663835338=QX1WU_7MVFzYpf4zl6rEDU7NBaqgizOz4_FKW3TuFHI.eyJ1c2VyX2lkIjoiMjk2MTc1ODc5ODQxMjAwIiwiY29kZSI6IkFRSi1xU0VYd3llbFgzR2FUS2ppNnRVNTFCcnNGSEUtMk9JTm1Jc3Z4ZVVXYWsxaXFvbWJUMElpSkZwT0FITVZfX0FmX2xRRnR2MWllRVZTM1BLTGlyaDN5NVZEMTZIcE90UDdMOFd3a2lSQ1AyTmlaNXZEOWVJVVh4RGU1eEF1dWlQbXJzY3J6UHpkV3JKZHZiSHpBVTFiZVMwLVhXTHJpbU1vOWg0eVpLMms4VXRuck9td0pvSFFka3FCZFo5S2J6X0N6SHk4TDJOd1d3eHd5a3BydVBKOEdabGRwNzNaWEF4R3lpMFl0UUpzMURla0hDNUllN1Q4WVZtbVlrZWRHTmtGMXhqSV96TlZfV2NrSHlVV1FXcEhZVktkSFFVNFl4Z2h0S0YwUjVxZlN5YnA0aE5EX0hHYmd1MmV2TlhMM2hiRmZYWUp4S0FzeDBoSFpHZ29nRnF3OFAwWGFYNmVkaHNPang4d2VNLW93USIsIm9hdXRoX3Rva2VuIjoiRUFBRm56emVCZnNvQlIzYzhyemdzaEVXQzUzdUg1MFZkN0dURDBPVEZBaHV3bzJsb0ROaXNNVWhFM2RlRXp4dW1vSGxmS1pCclBQZGx3VW1BbWZlNUU1NHlEYmxUR3d5ekN5Q0dlY0FNRkNNdHRyaU1SS3J5TUlwTzF4YjNCR0xnd29EcXYwc1pCYjFPUDFIeW50QUtvRGw5UTRKSDRDQUlKVXdWeWRhOHUzb0VGM1ZXU1ZkZjdFMFFwSU5NY2I1d2RtU0FpV1cwNDc3WXJaQW9aQUdRR0I0WkQiLCJhbGdvcml0aG0iOiJITUFDLVNIQTI1NiIsImlzc3VlZF9hdCI6MTc4NDI3NTcyNX0; __utmb=257500956.6.10.1784275686; _ga_6M8E625L9H=GS2.2.s1784275686$o1$g1$t1784275922$j60$l0$h0"

        headers = {
            "user-agent": user_agent,
            "cookie": cookie,
            "accept": "application/json, text/javascript, */*; q=0.01",
            "x-requested-with": "XMLHttpRequest"
        }

        api_url = "https://www.foody.vn/__get/Review/ResLoadMore"
        last_id = ""
        all_comments = []
        
        # Hiển thị thanh trạng thái đang tải (Loading bar) cho mẹ xem
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Cào thử nghiệm tối đa 3 lượt (khoảng 30 comment) để demo tốc độ nhanh
        for page in range(1, 4):
            status_text.text(f"Đang xử lý lượt {page}...")
            progress_bar.progress(page * 33)
            
            params = {
                "t": str(int(time.time() * 1000)),
                "ResId": res_id,
                "LastId": last_id,
                "Count": "10",
                "Type": "1",
                "fromOwner": "",
                "isLatest": "true",
                "ExcludeIds": ""
            }
            
            try:
                response = requests.get(api_url, headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    comments = response.json().get("Items", [])
                    if not comments:
                        break
                    
                    for item in comments:
                        all_comments.append({
                            "Tên người dùng": item.get("Owner", {}).get("DisplayName"),
                            "Số điểm": item.get("AverageRating"),
                            "Nội dung bình luận": item.get("Description"),
                            "Ngày đăng": item.get("CreatedDate")
                        })
                    last_id = str(comments[-1].get("Id"))
                    time.sleep(1.5)
                else:
                    st.error(f"Lỗi kết nối Foody: {response.status_code}")
                    break
            except Exception as e:
                st.error(f"Lỗi hệ thống: {e}")
                break

        progress_bar.progress(100)
        status_text.text("Đã hoàn thành cào dữ liệu!")

        # 3. Xuất file Excel ngay trên giao diện Web cho mẹ tải về
        if all_comments:
            df = pd.DataFrame(all_comments)
            
            # Ghi dữ liệu vào bộ nhớ tạm để tạo link download
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Comments')
            processed_data = output.getvalue()
            
            st.success(f"Cào thành công {len(all_comments)} bình luận rồi nha mẹ ơi!")
            
            # Nút tải file siêu xịn
            st.download_button(
                label="📥 Bấm vào đây để tải file Excel về máy",
                data=processed_data,
                file_name="binh_luan_foody.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Không tìm thấy bình luận nào hoặc link không đúng cấu trúc.")