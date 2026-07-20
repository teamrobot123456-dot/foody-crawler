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
    """Chuẩn hóa link Foody/ShopeeFood về trang quán Foody tương ứng."""
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


def _parse_human_count(raw: str | None) -> int | None:
    """Đổi 1.3K/1,3K/1.335 thành số nguyên hợp lý."""
    if raw is None:
        return None
    value = html.unescape(str(raw)).strip().lower().replace(" ", "")
    match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*([km]?)", value)
    if not match:
        return None

    number_text, suffix = match.groups()
    if suffix:
        # Foody hiển thị số rút gọn kiểu 1.3K hoặc 1,3K.
        number = float(number_text.replace(",", "."))
        multiplier = 1_000 if suffix == "k" else 1_000_000
        return int(round(number * multiplier))

    # Khi không có K/M, dấu chấm/phẩy thường là phân cách hàng nghìn.
    digits = re.sub(r"\D", "", number_text)
    return int(digits) if digits else None


def _visible_text(page_html: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", page_html, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_visible_review_count(page_html: str) -> int | None:
    """Ưu tiên con số hiển thị cạnh cụm 'bình luận', gồm cả dạng 1.3K."""
    text = _visible_text(page_html)
    matches = re.findall(
        r"(?<!\d)(\d+(?:[.,]\d+)?\s*[KkMm]?)\s*bình\s*luận",
        text,
        flags=re.IGNORECASE,
    )
    values = [value for value in (_parse_human_count(raw) for raw in matches) if value]
    # Không lấy max từ các biến ẩn như bản cũ; chỉ lấy con số hiển thị đầu tiên hợp lý.
    return values[0] if values else None


def _extract_review_breakdown(page_html: str) -> tuple[int | None, dict[str, int]]:
    """Đọc 4 nhóm đánh giá trên trang /binh-luan và cộng thành tổng chính xác."""
    text = _visible_text(page_html)
    labels = ["Tuyệt vời", "Khá tốt", "Trung bình", "Kém"]
    breakdown: dict[str, int] = {}

    for label in labels:
        escaped = re.escape(label)
        preceding: list[int] = []
        following: list[int] = []

        for raw in re.findall(
            rf"(?<!\d)(\d[\d.,]*)\s+{escaped}(?!\w)",
            text,
            flags=re.IGNORECASE,
        ):
            value = _parse_human_count(raw)
            if value is not None and 0 <= value <= 10_000_000:
                preceding.append(value)

        # Chỉ dùng dạng nhãn đứng trước số khi trang không có dạng số đứng trước nhãn.
        if not preceding:
            for raw in re.findall(
                rf"{escaped}\s+(\d[\d.,]*)(?!\w)",
                text,
                flags=re.IGNORECASE,
            ):
                value = _parse_human_count(raw)
                if value is not None and 0 <= value <= 10_000_000:
                    following.append(value)

        candidates = preceding or following
        if candidates:
            # Trang đôi khi lặp template với số 0; lấy giá trị lớn nhất của đúng nhãn.
            breakdown[label] = max(candidates)

    if len(breakdown) == 4:
        return sum(breakdown.values()), breakdown
    return None, breakdown


def resolve_foody_res_id(
    session: requests.Session,
    foody_url: str,
    timeout: int = 20,
) -> tuple[str, str, int | None, str, dict[str, int]]:
    """Mở trang quán, lấy ResId và tổng bình luận công bố."""
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
            "Hãy đợi một lúc rồi thử lại."
        )
    if response.status_code >= 400:
        raise CrawlerError(f"Không mở được trang quán trên Foody (HTTP {response.status_code}).")

    page_html = response.text
    cookie_values = [
        cookie.value for cookie in session.cookies if cookie.name.startswith("fd.res.view.")
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
            "Có thể Foody vừa thay đổi cấu trúc trang."
        )

    declared_count = _extract_visible_review_count(page_html)
    declared_source = "Con số hiển thị trên trang quán"
    breakdown: dict[str, int] = {}

    # Trang /binh-luan thường có 4 số chi tiết; tổng này chính xác hơn dạng rút gọn 1.3K.
    review_page_url = foody_url.rstrip("/") + "/binh-luan"
    try:
        review_response = session.get(
            review_page_url,
            headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8", "Referer": foody_url},
            timeout=timeout,
            allow_redirects=True,
        )
        if review_response.status_code < 400:
            exact_count, breakdown = _extract_review_breakdown(review_response.text)
            if exact_count is not None and exact_count > 0:
                declared_count = exact_count
                declared_source = "Tổng 4 nhóm trên trang /binh-luan"
    except requests.RequestException:
        pass

    return candidates[0], response.url, declared_count, declared_source, breakdown


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
    review_type: int,
    timeout: int,
) -> list[dict]:
    exclude_value = ",".join(exclude_ids[-100:])
    params = {
        "t": str(int(time.time() * 1000)),
        "ResId": str(res_id),
        "LastId": last_id,
        "Count": str(count),
        "Type": str(review_type),
        "fromOwner": "",
        "isLatest": "true" if is_latest else "false",
        "ExcludeIds": exclude_value,
    }
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": foody_url.rstrip("/") + "/binh-luan",
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
        raise CrawlerError(f"Endpoint bình luận trả về HTTP {response.status_code}.")
    try:
        payload = response.json()
    except ValueError as exc:
        preview = _clean_text(response.text[:250])
        raise CrawlerError(
            "Foody không trả về JSON như dự kiến. "
            f"Phản hồi bắt đầu bằng: {preview or '[rỗng]'}"
        ) from exc
    return _get_items(payload)


def _item_id(item: dict) -> str:
    return str(
        item.get("Id")
        or item.get("id")
        or item.get("ReviewId")
        or item.get("review_id")
        or ""
    )


def fetch_foody_reviews(
    session: requests.Session,
    res_id: str,
    foody_url: str,
    max_reviews: int | None = 100,
    declared_review_count: int | None = None,
    delay_seconds: float = 0.3,
    batch_size: int = 30,
    probe_review_types: bool = True,
    timeout: int = 20,
    progress_callback: Callable[[int], None] | None = None,
) -> tuple[list[dict], str, list[dict]]:
    """Tải bình luận qua nhiều cursor và thử các giá trị Type công khai.

    Foody có thể chỉ trả một cửa sổ khoảng 200 mục cho một luồng. Bản này không
    tuyên bố vượt giới hạn đó; nó thử các luồng Type độc lập và gộp ReviewId để
    thu được nhiều mục công khai nhất mà endpoint thực sự trả về.
    """
    if not str(res_id).isdigit():
        raise CrawlerError("Foody ResId không hợp lệ.")
    if max_reviews is not None:
        max_reviews = max(1, int(max_reviews))

    batch_size = max(10, min(int(batch_size), 50))
    target = max_reviews if max_reviews is not None else declared_review_count
    max_batches_total = 6000

    seen_keys: set[str] = set()
    ordered_ids: list[str] = []
    rows: list[dict] = []
    diagnostics: list[dict] = []
    total_batches = 0

    def target_reached() -> bool:
        return target is not None and len(rows) >= target

    def run_stream(
        *,
        name: str,
        review_type: int,
        is_latest: bool,
        start_last_id: str = "",
        use_exclude_ids: bool = False,
    ) -> str:
        nonlocal total_batches
        cursor = start_last_id
        response_signatures: set[tuple[str, ...]] = set()
        stagnant = 0
        stream_batch = 0

        while total_batches < max_batches_total and not target_reached():
            total_batches += 1
            stream_batch += 1
            exclude_ids = ordered_ids[-100:] if use_exclude_ids else []

            try:
                items = _request_review_batch(
                    session,
                    res_id=res_id,
                    foody_url=foody_url,
                    last_id=cursor,
                    is_latest=is_latest,
                    exclude_ids=exclude_ids,
                    count=batch_size,
                    review_type=review_type,
                    timeout=timeout,
                )
            except requests.RequestException as exc:
                raise CrawlerError(
                    f"Lỗi mạng ở chiến lược {name}, lượt {stream_batch}: {exc}"
                ) from exc

            ids = tuple(filter(None, (_item_id(item) for item in items)))
            signature = ids or tuple(repr(item) for item in items)

            if not items:
                diagnostics.append(
                    {
                        "strategy": name,
                        "type": review_type,
                        "batch": stream_batch,
                        "cursor_in": cursor,
                        "requested": batch_size,
                        "received": 0,
                        "new": 0,
                        "cursor_out": "",
                        "reason": "empty_response",
                    }
                )
                break

            if signature in response_signatures:
                diagnostics.append(
                    {
                        "strategy": name,
                        "type": review_type,
                        "batch": stream_batch,
                        "cursor_in": cursor,
                        "requested": batch_size,
                        "received": len(items),
                        "new": 0,
                        "cursor_out": _item_id(items[-1]),
                        "reason": "repeated_page",
                    }
                )
                break
            response_signatures.add(signature)

            added = 0
            for item in items:
                review_id = _item_id(item)
                # Nếu ID rỗng, dùng nội dung ổn định hơn repr đơn thuần.
                fallback_key = "|".join(
                    [
                        str(item.get("CreatedDate") or item.get("created_date") or ""),
                        str(item.get("Title") or item.get("title") or ""),
                        str(item.get("Description") or item.get("description") or ""),
                    ]
                )
                dedupe_key = f"id:{review_id}" if review_id else f"content:{fallback_key}"
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                if review_id:
                    ordered_ids.append(review_id)
                rows.append(_review_to_row(item, foody_url))
                added += 1
                if max_reviews is not None and len(rows) >= max_reviews:
                    break

            next_cursor = _item_id(items[-1])
            reason = "ok"
            if added == 0:
                stagnant += 1
                reason = "duplicates_only"
            else:
                stagnant = 0

            diagnostics.append(
                {
                    "strategy": name,
                    "type": review_type,
                    "batch": stream_batch,
                    "cursor_in": cursor,
                    "requested": batch_size,
                    "received": len(items),
                    "new": added,
                    "cursor_out": next_cursor,
                    "reason": reason,
                }
            )

            if progress_callback:
                progress_callback(len(rows))

            if target_reached():
                cursor = next_cursor or cursor
                break
            if not next_cursor or next_cursor == cursor:
                break
            if stagnant >= 2:
                break

            cursor = next_cursor
            time.sleep(max(0.0, delay_seconds))

        return cursor

    # Luồng cơ bản Type=1.
    latest_tail = run_stream(
        name="latest_cursor",
        review_type=1,
        is_latest=True,
        start_last_id="",
        use_exclude_ids=False,
    )
    if not target_reached():
        run_stream(
            name="oldest_cursor",
            review_type=1,
            is_latest=False,
            start_last_id="",
            use_exclude_ids=False,
        )
    if not target_reached() and latest_tail:
        run_stream(
            name="older_from_latest_tail",
            review_type=1,
            is_latest=False,
            start_last_id=latest_tail,
            use_exclude_ids=False,
        )
    if not target_reached() and ordered_ids:
        run_stream(
            name="oldest_with_exclude_fallback",
            review_type=1,
            is_latest=False,
            start_last_id="",
            use_exclude_ids=True,
        )

    # Quét mở rộng: Type là tham số nội bộ, chưa có tài liệu công khai. Ta chỉ
    # thử các giá trị nhỏ, gộp ID và dừng ngay khi endpoint rỗng/lặp.
    if probe_review_types and not target_reached():
        for review_type in (0, 2, 3, 4, 5):
            if target_reached():
                break
            run_stream(
                name=f"type_{review_type}_latest",
                review_type=review_type,
                is_latest=True,
                start_last_id="",
                use_exclude_ids=False,
            )
            if not target_reached():
                run_stream(
                    name=f"type_{review_type}_oldest",
                    review_type=review_type,
                    is_latest=False,
                    start_last_id="",
                    use_exclude_ids=False,
                )

    if max_reviews is not None and len(rows) >= max_reviews:
        stop_reason = f"Đã đạt giới hạn {max_reviews} bình luận do người dùng đặt."
    elif declared_review_count is not None and len(rows) >= declared_review_count:
        stop_reason = (
            f"Đã thu thập đủ {len(rows)}/{declared_review_count} bình luận "
            "theo tổng Foody công bố."
        )
    elif declared_review_count is not None:
        stop_reason = (
            f"Foody công bố khoảng {declared_review_count} bình luận nhưng các luồng "
            f"endpoint công khai hiện chỉ trả {len(rows)} mục duy nhất. "
            "Đây là giới hạn/phân trang phía Foody, không phải ô giới hạn của ứng dụng."
        )
    else:
        stop_reason = "Đã tải hết các mục duy nhất mà endpoint công khai Foody trả về."

    result = rows if max_reviews is None else rows[:max_reviews]
    return result, stop_reason, diagnostics


def crawl_public_reviews(
    raw_url: str,
    max_reviews: int | None = 100,
    delay_seconds: float = 0.3,
    batch_size: int = 30,
    probe_review_types: bool = True,
    progress_callback: Callable[[int], None] | None = None,
) -> tuple[list[dict], dict]:
    normalized = normalize_restaurant_url(raw_url)
    session = build_session()
    foody_url, mapping_method = discover_foody_url_from_shopeefood(session, normalized)
    (
        res_id,
        resolved_url,
        declared_review_count,
        declared_count_source,
        review_breakdown,
    ) = resolve_foody_res_id(session, foody_url)

    rows, stop_reason, diagnostics = fetch_foody_reviews(
        session=session,
        res_id=res_id,
        foody_url=foody_url,
        max_reviews=max_reviews,
        declared_review_count=declared_review_count,
        delay_seconds=delay_seconds,
        batch_size=batch_size,
        probe_review_types=probe_review_types,
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
        "declared_count_source": declared_count_source,
        "review_breakdown": review_breakdown,
        "collection_mode": "Toàn bộ" if max_reviews is None else f"Tối đa {max_reviews}",
        "review_count": len(rows),
        "batch_size_requested": batch_size,
        "delay_seconds": delay_seconds,
        "probe_review_types": probe_review_types,
        "source_scope": "Bình luận chữ công khai trên Foody",
        "pagination_diagnostics": diagnostics,
        "stop_reason": stop_reason,
    }
    return rows, metadata
