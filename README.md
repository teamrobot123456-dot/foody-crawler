# Foody Crawler (Streamlit)

Ứng dụng nhận link trang quán Foody hoặc ShopeeFood, chuẩn hóa về trang Foody tương ứng, tải bình luận văn bản công khai và xuất Excel.

## Chạy trên Streamlit Community Cloud

1. Đưa toàn bộ các file trong thư mục này lên repository GitHub.
2. Trên Streamlit Community Cloud, chọn repository và đặt **Main file path** là `app.py`.
3. Deploy lại ứng dụng.

## Chạy cục bộ

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Chạy dòng lệnh

```bash
python crawl_foody.py "https://www.foody.vn/ha-noi/ten-quan" --max 100 --output ket_qua.xlsx
```

## Lưu ý

- Không lưu cookie, token đăng nhập hoặc mật khẩu trong mã nguồn.
- Với link ShopeeFood, ứng dụng ưu tiên đọc liên kết Foody xuất hiện trên trang quán; nếu không thấy, ứng dụng thử ánh xạ theo cùng tỉnh/thành và slug. Kết quả là bình luận văn bản công khai từ Foody.
- Endpoint của nền tảng có thể thay đổi. Khi lỗi xảy ra, ứng dụng hiển thị mã HTTP và phản hồi kỹ thuật thay vì che giấu lỗi.
- Thu thập với số lượng hợp lý và tuân thủ điều khoản sử dụng của nền tảng.
