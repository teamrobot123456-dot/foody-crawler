from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.parse import unquote, urlparse

import requests


FOODY_REVIEW_ENDPOINT = "https://www.foody.vn/__get/Review/ResLoadMore"
ALLOWED_HOSTS = {
    "foody.vn",
    "www.foody.vn",
    "shopeefood.vn",
    "www.shopeefood.vn",
}


class CrawlerError(RuntimeError):
    """Lỗi có thể hiển thị trực tiếp cho người dùng."""


@dataclass(frozen=True)
class NormalizedRestaurantURL:
    original_url: str
    foody_url: str
    input_platform: str
    city_slug: str
    restaurant_slug: str


def normalize_restaurant_url(raw_url: str) -> NormalizedRestaurantURL:
    """Chuẩn hóa link Foody/ShopeeFood về trang quán Foody tương ứng.

    Hàm chấp nhận cả link trang chính, /binh-luan, /thuc-don và link có query string.
    """
    value = (raw_url or "").strip()
    if not value:
        raise CrawlerError("Bạn chưa nhập link quán.")

    if not re.match(r"^https?://", value, flags=re.IGNORECASE):
        value = "https://" + value

    parsed = urlparse(value)
    host = parsed.netloc.lower().split(":", 1)[0]
    if host not in ALLOWED_HOSTS:
        raise CrawlerError(
            "Link phải thuộc foody.vn hoặc shopeefood.vn. "
            "Không dán link tìm kiếm, link bản đồ hoặc link rút gọn."
        )

    path_parts = [unquote(part).strip() for part in parsed.path.split("/") if part.strip()]
    if len(path_parts) < 2:
        raise CrawlerError(
            "Link chưa phải trang chi tiết của một quán. "
            "Link hợp lệ thường có dạng /tinh-thanh/ten-quan."
        )

    city_slug, restaurant_slug = path_parts[0], path_parts[1]
    if restaurant_slug.lower() in {"binh-luan", "thuc-don", "hinh-anh"}:
        raise CrawlerError("Không xác định được tên quán từ link đã nhập.")

    platform = "ShopeeFood" if "shopeefood" in host else "Foody"
    foody_url = f"https://www.foody.vn/{city_slug}/{restaurant_slug}"

    return NormalizedRestaurantURL(
        original_url=value,
        foody_url=foody_url,
        input_platform=platform,
        city_slug=city_slug,
        restaurant_slug=restaurant_slug,
    )


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    )
    return session


def discover_foody_url_from_shopeefood(
    session: requests.Session,
    normalized: NormalizedRestaurantURL,
    timeout: int = 20,
) -> tuple[str, str]:
    """Tìm link Foody được ShopeeFood liên kết; nếu không thấy thì dùng cùng path."""
    if normalized.input_platform != "ShopeeFood":
        return normalized.foody_url, "Link đầu vào là Foody"

    try:
        response = session.get(
            normalized.original_url,
            headers={
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                )
            },
            timeout=timeout,
            allow_redirects=True,
        )
        if response.status_code < 400:
            page_html = html.unescape(response.text)
            hrefs = re.findall(
                r"href\s*=\s*['\"](https?://(?:www\.)?foody\.vn/[^'\"<>\s]+)['\"]",
                page_html,
                flags=re.IGNORECASE,
            )
            for href in hrefs:
                try:
                    candidate = normalize_restaurant_url(href)
                except CrawlerError:
                    continue
                return candidate.foody_url, "Link Foody được tìm thấy trong trang ShopeeFood"
    except requests.RequestException:
        pass

    return normalized.foody_url, "Ánh xạ ShopeeFood sang Foody theo cùng tỉnh/thành và slug"


def _numeric_candidates(values: Iterable[str | None]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        candidate = str(value).strip().strip('"\'')
        if candidate.isdigit() and int(candidate) > 0:
            result.append(candidate)
    return result


def _extract_declared_review_count(page_html: str) -> int | None:
    """Đọc tổng số bình luận mà trang Foody công bố, nếu tìm thấy."""
    patterns = [
        r"([\d.,]+)\s*bình\s*luận",
        r"ReviewCount[\"']?\s*[:=]\s*[\"']?([\d.,]+)",
        r"TotalReview[\"']?\s*[:=]\s*[\"']?([\d.,]+)",
    ]
    values: list[int] = []
    for pattern in patterns:
        for raw in re.findall(pattern, page_html, flags=re.IGNORECASE):
            digits = re.sub(r"\D", "", str(raw))
            if digits:
                values.append(int(digits))
    return max(values) if values else None


def resolve_foody_res_id(
    session: requests.Session,
    foody_url: str,
    timeout: int = 20,
) -> tuple[str, str, int | None]:
    """Mở trang quán, lấy Foody ResId và tổng số bình luận được công bố."""
    try:
        response = session.get(
            foody_url,
            headers={
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                )
            },
            timeout=timeout,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        raise CrawlerError(f"Không kết nối được tới Foody: {exc}") from exc

    if response.status_code == 404:
        raise CrawlerError("Foody trả về 404: không tìm thấy trang quán tương ứng.")
    if response.status_code in {403, 429}:
        raise CrawlerError(
            f"Foody tạm từ chối yêu cầu (HTTP {response.status_code}). "
            "Hãy đợi một lúc rồi thử lại với số lượng nhỏ hơn."
        )
    if response.status_code >= 400:
        raise CrawlerError(f"Không mở được trang quán trên Foody (HTTP {response.status_code}).")

    page_html = response.text

    cookie_values = [
        cookie.value
        for cookie in session.cookies
        if cookie.name.startswith("fd.res.view.")
    ]
    candidates = _numeric_candidates(cookie_values)

    patterns = [
        r"fd\.res\.view\.\d+\s*=\s*(\d+)",
        r"[\"']ResId[\"']\s*[:=]\s*[\"']?(\d+)",
        r"[\"']resId[\"']\s*[:=]\s*[\"']?(\d+)",
        r"[\"']RestaurantId[\"']\s*[:=]\s*[\"']?(\d+)",
        r"[\"']restaurant_id[\"']\s*[:=]\s*[\"']?(\d+)",
        r"data-res(?:taurant)?-id\s*=\s*[\"'](\d+)[\"']",
    ]
    for pattern in patterns:
        candidates.extend(re.findall(pattern, page_html, flags=re.IGNORECASE))

    candidates = _numeric_candidates(candidates)
    if not candidates:
        raise CrawlerError(
            "Đã mở được trang quán nhưng không tìm thấy Foody ResId. "
            "Có thể link ShopeeFood này không có trang Foody tương ứng, "
            "hoặc Foody vừa thay đổi cấu trúc trang."
        )

    declared_count = _extract_declared_review_count(page_html)
    return candidates[0], response.url, declared_count

def _clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _get_items(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        return []

    direct_keys = ("Items", "items", "ReplyInfos", "reply_infos")
    for key in direct_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    for container_key in ("Data", "data", "Result", "result", "Reply", "reply"):
        nested = payload.get(container_key)
        if isinstance(nested, dict):
            for key in direct_keys:
                value = nested.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
    return []


def _review_to_row(item: dict, foody_url: str) -> dict:
    owner = item.get("Owner") or item.get("owner") or item.get("User") or item.get("user") or {}
    if not isinstance(owner, dict):
        owner = {}

    review_id = item.get("Id") or item.get("id") or item.get("ReviewId") or item.get("review_id")
    title = item.get("Title") or item.get("title") or ""
    description = (
        item.get("Description")
        or item.get("description")
        or item.get("Message")
        or item.get("message")
        or ""
    )
    rating = (
        item.get("AverageRating")
        if item.get("AverageRating") is not None
        else item.get("average_rating", item.get("Rating", item.get("rating", "")))
    )
    created = (
        item.get("CreatedDate")
        or item.get("created_date")
        or item.get("CreatedOnTimeDiff")
        or item.get("created_on_time_diff")
        or ""
    )

    return {
        "Mã bình luận": str(review_id or ""),
        "Tên người dùng": _clean_text(
            owner.get("DisplayName")
            or owner.get("display_name")
            or owner.get("Name")
            or owner.get("name")
            or "Ẩn danh"
        ),
        "Điểm đánh giá": rating,
        "Tiêu đề": _clean_text(title),
        "Nội dung bình luận": _clean_text(description),
        "Ngày đăng": _clean_text(created),
        "Thiết bị đăng": _clean_text(item.get("DeviceName") or item.get("device_name") or ""),
        "Nguồn": "Foody",
        "Link quán": foody_url,
        "Link bình luận": f"{foody_url}/binh-luan-{review_id}" if review_id else "",
    }


def _request_review_batch(
    session: requests.Session,
    *,
    res_id: str,
    foody_url: str,
    last_id: str,
    is_latest: bool,
    exclude_ids: list[str],
    count: int,
    timeout: int,
) -> list[dict]:
    # Foody dùng ExcludeIds cho các bình luận đã hiện. Chỉ gửi một cửa sổ gần nhất
    # để URL không quá dài. Endpoint là nội bộ nên cấu trúc có thể thay đổi.
    exclude_value = ",".join(exclude_ids[-100:])
    params = {
        "t": str(int(time.time() * 1000)),
        "ResId": str(res_id),
        "LastId": last_id,
        "Count": str(count),
        "Type": "1",
        "fromOwner": "",
        "isLatest": "true" if is_latest else "false",
        "ExcludeIds": exclude_value,
    }
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": foody_url,
    }
    response = session.get(
        FOODY_REVIEW_ENDPOINT,
        params=params,
        headers=headers,
        timeout=timeout,
    )
    if response.status_code in {403, 429}:
        raise CrawlerError(
            f"Foody tạm giới hạn yêu cầu (HTTP {response.status_code}). "
            "Dữ liệu có thể chưa được tải đầy đủ."
        )
    if response.status_code >= 400:
        raise CrawlerError(
            f"Endpoint bình luận trả về HTTP {response.status_code}."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        preview = _clean_text(response.text[:250])
        raise CrawlerError(
            "Foody không trả về JSON như dự kiến. "
            f"Phản hồi bắt đầu bằng: {preview or '[rỗng]'}"
        ) from exc
    return _get_items(payload)


def fetch_foody_reviews(
    session: requests.Session,
    res_id: str,
    foody_url: str,
    max_reviews: int | None = 100,
    declared_review_count: int | None = None,
    delay_seconds: float = 0.8,
    timeout: int = 20,
    progress_callback: Callable[[int], None] | None = None,
) -> tuple[list[dict], str]:
    """Tải bình luận công khai và thử hai chế độ phân trang của Foody.

    Foody đôi khi dừng đúng ở 100 mục khi dùng isLatest=true. Khi tổng công bố
    trên trang lớn hơn số đã lấy, hàm chuyển sang isLatest=false và gửi ExcludeIds
    để thử lấy phần bình luận cũ hơn mà không vượt qua đăng nhập.
    """
    if not str(res_id).isdigit():
        raise CrawlerError("Foody ResId không hợp lệ.")
    if max_reviews is not None:
        max_reviews = max(1, int(max_reviews))

    target = max_reviews if max_reviews is not None else declared_review_count
    max_pages = 5000
    seen_ids: set[str] = set()
    ordered_ids: list[str] = []
    rows: list[dict] = []
    last_id = ""
    page_number = 0
    stagnant_batches = 0

    # Chế độ 1: mới nhất. Chế độ 2: bình luận cũ hơn.
    modes = [True, False]
    for is_latest in modes:
        # Khi chuyển chế độ, thử tiếp từ cursor cũ; nếu không có dữ liệu sẽ thử lại từ đầu
        # với ExcludeIds để Foody bỏ qua các mục đã nhận.
        mode_last_id = last_id
        restarted_without_cursor = False

        while page_number < max_pages:
            if target is not None and len(rows) >= target:
                break
            page_number += 1
            try:
                items = _request_review_batch(
                    session,
                    res_id=res_id,
                    foody_url=foody_url,
                    last_id=mode_last_id,
                    is_latest=is_latest,
                    exclude_ids=ordered_ids,
                    count=10,
                    timeout=timeout,
                )
            except requests.RequestException as exc:
                raise CrawlerError(f"Lỗi khi tải lượt {page_number}: {exc}") from exc

            if not items:
                # Một số phiên Foody không chấp nhận cursor của chế độ latest khi đổi
                # sang old. Thử lại một lần từ đầu nhưng giữ ExcludeIds.
                if not is_latest and mode_last_id and not restarted_without_cursor:
                    mode_last_id = ""
                    restarted_without_cursor = True
                    time.sleep(max(0.0, delay_seconds))
                    continue
                break

            added_this_batch = 0
            for item in items:
                review_id = str(
                    item.get("Id")
                    or item.get("id")
                    or item.get("ReviewId")
                    or item.get("review_id")
                    or ""
                )
                dedupe_key = review_id or repr(item)
                if dedupe_key in seen_ids:
                    continue
                seen_ids.add(dedupe_key)
                if review_id:
                    ordered_ids.append(review_id)
                rows.append(_review_to_row(item, foody_url))
                added_this_batch += 1
                if max_reviews is not None and len(rows) >= max_reviews:
                    break

            if progress_callback:
                progress_callback(len(rows))

            next_last_id = str(
                items[-1].get("Id")
                or items[-1].get("id")
                or items[-1].get("ReviewId")
                or items[-1].get("review_id")
                or ""
            )

            if added_this_batch == 0:
                stagnant_batches += 1
            else:
                stagnant_batches = 0

            if next_last_id and next_last_id != mode_last_id:
                mode_last_id = next_last_id
                last_id = next_last_id
            elif added_this_batch == 0:
                stagnant_batches += 1

            if stagnant_batches >= 3:
                break
            time.sleep(max(0.0, delay_seconds))

        if target is not None and len(rows) >= target:
            break

    if max_reviews is not None and len(rows) >= max_reviews:
        stop_reason = f"Đã đạt giới hạn {max_reviews} bình luận do người dùng đặt."
    elif declared_review_count is not None and len(rows) >= declared_review_count:
        stop_reason = (
            f"Đã thu thập đủ {len(rows)}/{declared_review_count} bình luận theo tổng số Foody công bố."
        )
    elif declared_review_count is not None and len(rows) < declared_review_count:
        stop_reason = (
            f"Foody công bố {declared_review_count} bình luận nhưng endpoint công khai chỉ trả về "
            f"{len(rows)} bình luận trong phiên này. Phần còn lại có thể là dữ liệu cũ/ẩn, "
            "đã bị gỡ hoặc chỉ được trả về trong phiên đăng nhập; ứng dụng không vượt qua đăng nhập."
        )
    else:
        stop_reason = "Đã tải hết dữ liệu mà endpoint công khai Foody trả về trong phiên này."

    return rows if max_reviews is None else rows[:max_reviews], stop_reason

def crawl_public_reviews(
    raw_url: str,
    max_reviews: int | None = 100,
    delay_seconds: float = 0.8,
    progress_callback: Callable[[int], None] | None = None,
) -> tuple[list[dict], dict]:
    normalized = normalize_restaurant_url(raw_url)
    session = build_session()
    foody_url, mapping_method = discover_foody_url_from_shopeefood(session, normalized)
    res_id, resolved_url, declared_review_count = resolve_foody_res_id(session, foody_url)
    rows, stop_reason = fetch_foody_reviews(
        session=session,
        res_id=res_id,
        foody_url=foody_url,
        max_reviews=max_reviews,
        declared_review_count=declared_review_count,
        delay_seconds=delay_seconds,
        progress_callback=progress_callback,
    )
    metadata = {
        "input_platform": normalized.input_platform,
        "input_url": normalized.original_url,
        "foody_url": foody_url,
        "mapping_method": mapping_method,
        "resolved_url": resolved_url,
        "res_id": res_id,
        "declared_review_count": declared_review_count,
        "collection_mode": "Toàn bộ" if max_reviews is None else f"Tối đa {max_reviews}",
        "review_count": len(rows),
        "stop_reason": stop_reason,
    }
    return rows, metadata

