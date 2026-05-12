#!/usr/bin/env python3
"""Search Reddit stories by keywords and save every unique story as a TXT file.

The script can read all settings from config.json. If Reddit API credentials are
filled in the config, it searches through Reddit OAuth. If the credentials are
empty, it falls back to Reddit's public JSON search endpoint.
"""

from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import hashlib
import json
import re
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
DEFAULT_CONFIG_PATH = "config.json"
DEFAULT_USER_AGENT = "RedditStoryParser/1.0 by your_reddit_username"
DEFAULT_CONFIG: dict[str, Any] = {
    "reddit": {
        "client_id": "",
        "client_secret": "",
        "username": "",
        "password": "",
        "user_agent": DEFAULT_USER_AGENT,
    },
    "search": {
        "keywords": ["заработок", "история успеха", "разочарование"],
        "subreddit": "",
        "limit": 25,
        "sort": "relevance",
        "time_filter": "all",
    },
    "saving": {
        "output_dir": "stories",
        "min_chars": 1000,
        "max_chars": 10_000,
        "sleep_seconds": 1.0,
        "skip_nsfw": True,
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find Reddit text posts by keywords and save unique stories to TXT files. "
            "Settings are read from config.json by default."
        )
    )
    parser.add_argument(
        "keywords",
        nargs="*",
        help="Keywords for Reddit search. Overrides search.keywords from config.json.",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="Path to JSON config file (default: config.json).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Folder where TXT files will be saved. Overrides saving.output_dir.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of Reddit posts to request. Overrides search.limit.",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        help="Minimum story length in characters. Overrides saving.min_chars.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        help="Maximum story length to save in characters. Overrides saving.max_chars.",
    )
    parser.add_argument(
        "--sort",
        choices=("relevance", "hot", "top", "new", "comments"),
        help="Reddit search sorting mode. Overrides search.sort.",
    )
    parser.add_argument(
        "--time",
        dest="time_filter",
        choices=("hour", "day", "week", "month", "year", "all"),
        help="Time filter for Reddit search. Overrides search.time_filter.",
    )
    parser.add_argument(
        "--subreddit",
        help="Optional subreddit name to search inside. Overrides search.subreddit.",
    )
    parser.add_argument(
        "--sleep",
        dest="sleep_seconds",
        type=float,
        help="Pause in seconds before saving the next story. Overrides saving.sleep_seconds.",
    )
    parser.add_argument(
        "--user-agent",
        help="HTTP/API User-Agent sent to Reddit. Overrides reddit.user_agent.",
    )
    return parser.parse_args(argv)


def deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = defaults.copy()
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        print(f"Config file not found: {path}. Using built-in defaults.")
        return copy.deepcopy(DEFAULT_CONFIG)

    try:
        user_config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Ошибка чтения JSON config-файла {path}: {exc}") from exc

    if not isinstance(user_config, dict):
        raise SystemExit(f"Config file {path} must contain a JSON object.")

    return deep_merge(copy.deepcopy(DEFAULT_CONFIG), user_config)


def apply_cli_overrides(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if args.keywords:
        config["search"]["keywords"] = args.keywords
    if args.output_dir is not None:
        config["saving"]["output_dir"] = args.output_dir
    if args.limit is not None:
        config["search"]["limit"] = args.limit
    if args.min_chars is not None:
        config["saving"]["min_chars"] = args.min_chars
    if args.max_chars is not None:
        config["saving"]["max_chars"] = args.max_chars
    if args.sort is not None:
        config["search"]["sort"] = args.sort
    if args.time_filter is not None:
        config["search"]["time_filter"] = args.time_filter
    if args.subreddit is not None:
        config["search"]["subreddit"] = args.subreddit
    if args.sleep_seconds is not None:
        config["saving"]["sleep_seconds"] = args.sleep_seconds
    if args.user_agent is not None:
        config["reddit"]["user_agent"] = args.user_agent
    return config


def build_query(keywords: Iterable[str]) -> str:
    words = [str(word).strip() for word in keywords if str(word).strip()]
    if not words:
        entered = input("Введите ключевые слова через пробел: ").strip()
        words = entered.split()
    if not words:
        raise SystemExit("Нужно указать хотя бы одно ключевое слово в config.json или аргументах запуска.")
    return " ".join(words)


def configured_reddit_login(reddit_config: dict[str, Any]) -> bool:
    required = ("client_id", "client_secret", "username", "password")
    return all(str(reddit_config.get(key, "")).strip() for key in required)


def fetch_reddit_oauth_token(reddit_config: dict[str, Any]) -> str:
    credentials = f"{reddit_config['client_id']}:{reddit_config['client_secret']}"
    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    data = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "username": str(reddit_config["username"]).strip(),
            "password": str(reddit_config["password"]).strip(),
        }
    ).encode("utf-8")
    user_agent = str(reddit_config.get("user_agent") or DEFAULT_USER_AGENT)
    request = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token",
        data=data,
        headers={
            "Authorization": f"Basic {encoded_credentials}",
            "User-Agent": user_agent,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Reddit OAuth вернул HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Не удалось подключиться к Reddit OAuth: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit("Reddit OAuth вернул ответ, который не похож на JSON.") from exc

    access_token = payload.get("access_token")
    if not access_token:
        raise SystemExit(f"Reddit OAuth не вернул access_token: {payload}")
    return str(access_token)


def fetch_reddit_posts_oauth(config: dict[str, Any], query: str, limit: int) -> list[dict[str, Any]]:
    reddit_config = config["reddit"]
    search_config = config["search"]
    access_token = fetch_reddit_oauth_token(reddit_config)
    params = {
        "q": query,
        "limit": str(limit),
        "sort": str(search_config["sort"]),
        "t": str(search_config["time_filter"]),
        "type": "link",
        "raw_json": "1",
    }

    subreddit_name = str(search_config.get("subreddit") or "").strip()
    if subreddit_name:
        base_url = f"https://oauth.reddit.com/r/{urllib.parse.quote(subreddit_name)}/search"
        params["restrict_sr"] = "1"
    else:
        base_url = "https://oauth.reddit.com/search"

    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    user_agent = str(reddit_config.get("user_agent") or DEFAULT_USER_AGENT)
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "User-Agent": user_agent,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Reddit API вернул HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Не удалось подключиться к Reddit API: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit("Reddit API вернул ответ, который не похож на JSON.") from exc

    children = payload.get("data", {}).get("children", [])
    return [child.get("data", {}) for child in children]


def fetch_reddit_posts(config: dict[str, Any], query: str) -> list[dict[str, Any]]:
    reddit_config = config["reddit"]
    search_config = config["search"]
    limit = max(1, min(int(search_config["limit"]), 100))

    if configured_reddit_login(reddit_config):
        print("Использую вход через Reddit API из config.json.")
        return fetch_reddit_posts_oauth(config, query, limit)

    print("Данные входа Reddit не заполнены. Использую публичный JSON endpoint без авторизации.")
    return fetch_reddit_posts_public(config, query, limit)


def fetch_reddit_posts_public(config: dict[str, Any], query: str, limit: int) -> list[dict[str, Any]]:
    search_config = config["search"]
    reddit_config = config["reddit"]
    params = {
        "q": query,
        "limit": str(limit),
        "sort": str(search_config["sort"]),
        "t": str(search_config["time_filter"]),
        "type": "link",
        "raw_json": "1",
    }

    subreddit_name = str(search_config.get("subreddit") or "").strip()
    if subreddit_name:
        base_url = f"https://www.reddit.com/r/{urllib.parse.quote(subreddit_name)}/search.json"
        params["restrict_sr"] = "1"
    else:
        base_url = REDDIT_SEARCH_URL

    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    user_agent = str(reddit_config.get("user_agent") or DEFAULT_USER_AGENT)
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Reddit вернул HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Не удалось подключиться к Reddit: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit("Reddit вернул ответ, который не похож на JSON.") from exc

    children = payload.get("data", {}).get("children", [])
    return [child.get("data", {}) for child in children]


def normalize_story_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def story_hash(title: str, text: str) -> str:
    normalized = re.sub(r"\s+", " ", f"{title}\n{text}".strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_existing_signatures(output_dir: Path) -> tuple[set[str], set[str]]:
    reddit_ids: set[str] = set()
    content_hashes: set[str] = set()

    if not output_dir.exists():
        return reddit_ids, content_hashes

    for path in output_dir.glob("*.txt"):
        try:
            head = path.read_text(encoding="utf-8", errors="ignore")[:2000]
        except OSError:
            continue

        reddit_id = re.search(r"^Reddit ID:\s*(\S+)", head, re.MULTILINE)
        content_hash = re.search(r"^Content hash:\s*(\S+)", head, re.MULTILINE)
        if reddit_id:
            reddit_ids.add(reddit_id.group(1))
        if content_hash:
            content_hashes.add(content_hash.group(1))

    return reddit_ids, content_hashes


def safe_filename(value: str, max_length: int = 90) -> str:
    value = re.sub(r"[^\w\-. ]+", "", value, flags=re.UNICODE)
    value = re.sub(r"\s+", "_", value.strip())
    value = value.strip("._")
    return (value or "reddit_story")[:max_length]


def format_timestamp(unix_timestamp: float | int | None) -> str:
    if not unix_timestamp:
        return "unknown"
    return dt.datetime.fromtimestamp(float(unix_timestamp), tz=dt.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def story_to_file_text(post: dict[str, Any], text: str, content_hash: str) -> str:
    title = post.get("title") or "Untitled"
    reddit_id = post.get("id") or "unknown"
    permalink = post.get("permalink") or ""
    reddit_url = f"https://www.reddit.com{permalink}" if permalink else post.get("url", "")
    original_url = post.get("url") or reddit_url

    header = f"""Title: {title}
Reddit ID: {reddit_id}
Content hash: {content_hash}
Subreddit: r/{post.get('subreddit', 'unknown')}
Author: u/{post.get('author', 'unknown')}
Created: {format_timestamp(post.get('created_utc'))}
Score: {post.get('score', 0)}
Comments: {post.get('num_comments', 0)}
Reddit URL: {reddit_url}
Original URL: {original_url}
Saved at: {dt.datetime.now(tz=dt.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}

--- STORY ---
"""
    return f"{header}{text}\n"


def save_story(output_dir: Path, post: dict[str, Any], text: str, content_hash: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    title = post.get("title") or "Untitled"
    reddit_id = post.get("id") or content_hash[:10]
    filename = f"{safe_filename(title)}_{reddit_id}.txt"
    path = output_dir / filename

    counter = 2
    while path.exists():
        path = output_dir / f"{safe_filename(title)}_{reddit_id}_{counter}.txt"
        counter += 1

    path.write_text(story_to_file_text(post, text, content_hash), encoding="utf-8")
    return path


def is_self_text_post(post: dict[str, Any], skip_nsfw: bool) -> bool:
    if skip_nsfw and post.get("over_18", False):
        return False
    return bool(post.get("is_self"))


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_config(Path(args.config)), args)
    query = build_query(config["search"].get("keywords", []))
    saving_config = config["saving"]
    output_dir = Path(str(saving_config["output_dir"]))
    min_chars = int(saving_config["min_chars"])
    max_chars = int(saving_config["max_chars"])
    sleep_seconds = float(saving_config["sleep_seconds"])
    skip_nsfw = bool(saving_config.get("skip_nsfw", True))
    existing_ids, existing_hashes = load_existing_signatures(output_dir)

    print(f"Ищу истории по запросу: {query!r}")
    posts = fetch_reddit_posts(config, query)
    print(f"Получено постов из поиска Reddit: {len(posts)}")

    saved = 0
    skipped = 0

    for post in posts:
        if not is_self_text_post(post, skip_nsfw):
            skipped += 1
            continue

        title = post.get("title") or "Untitled"
        reddit_id = post.get("id") or ""
        text = normalize_story_text(post.get("selftext") or "")

        if len(text) < min_chars:
            skipped += 1
            continue

        if max_chars > 0 and len(text) > max_chars:
            text = text[:max_chars].rstrip() + "\n\n[Story truncated by saving.max_chars]"

        content_hash = story_hash(title, text)
        if reddit_id in existing_ids or content_hash in existing_hashes:
            print(f"Пропуск дубликата: {title}")
            skipped += 1
            continue

        path = save_story(output_dir, post, text, content_hash)
        existing_ids.add(reddit_id)
        existing_hashes.add(content_hash)
        saved += 1
        print(f"Сохранено: {path}")
        time.sleep(max(0.0, sleep_seconds))

    summary = textwrap.dedent(
        f"""
        Готово.
        Сохранено новых историй: {saved}
        Пропущено постов: {skipped}
        Папка: {output_dir.resolve()}
        """
    ).strip()
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
