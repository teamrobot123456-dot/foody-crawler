from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from foody_client import CrawlerError, crawl_public_reviews


def main() -> int:
    parser = argparse.ArgumentParser(description="Tải bình luận công khai từ một trang quán Foody/ShopeeFood.")
    parser.add_argument("url", help="Link trang quán Foody hoặc ShopeeFood")
    parser.add_argument("--max", type=int, default=100, dest="max_reviews", help="Số bình luận tối đa")
    parser.add_argument("--output", default="binh_luan_foody.xlsx", help="Tên file Excel đầu ra")
    args = parser.parse_args()

    try:
        rows, metadata = crawl_public_reviews(args.url, max_reviews=args.max_reviews)
    except CrawlerError as exc:
        print(f"LỖI: {exc}")
        return 1

    if not rows:
        print("Không có bình luận văn bản để xuất.")
        return 2

    output_path = Path(args.output)
    pd.DataFrame(rows).to_excel(output_path, index=False)
    print(f"Đã lưu {len(rows)} bình luận vào: {output_path.resolve()}")
    print(f"Foody ResId: {metadata['res_id']}")
    print(metadata["stop_reason"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
