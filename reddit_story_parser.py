#!/usr/bin/env python3
"""Search Reddit stories by keywords and save every unique story as TXT."""

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
from typing import Any, Callable, Iterable

REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
DEFAULT_CONFIG_PATH = "config.json"
DEFAULT_USER_AGENT = "windows:reddit-story-parser:1.0 (by u/GAVRS1)"
DEFAULT_CONFIG: dict[str, Any] = {
    "reddit": {
        "access_token": "",
        "cookie": "",
        "client_id": "",
        "client_secret": "",
        "username": "",
        "password": "",
        "user_agent": DEFAULT_USER_AGENT,
    },
    "search": {
        "keywords": ["marriage", "disappointment", "bad relationship"],
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

LogCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int], None]
ResultCallback = Callable[[dict[str, Any]], None]
StopCallback = Callable[[], bool]


class PublicRedditSearchBlockedError(RuntimeError):
    """Raised when Reddit blocks unauthenticated public JSON search."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find Reddit text posts by keywords and save unique stories to TXT files."
    )
    parser.add_argument("keywords", nargs="*", help="Keywords for Reddit search.")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to JSON config file.")
    parser.add_argument("-o", "--output-dir", help="Folder where TXT files will be saved.")
    parser.add_argument("--limit", type=int, help="Maximum number of Reddit posts to request.")
    parser.add_argument("--min-chars", type=int, help="Minimum story length in characters.")
    parser.add_argument("--max-chars", type=int, help="Maximum story length to save in characters.")
    parser.add_argument("--sort", choices=("relevance", "hot", "top", "new", "comments"))
    parser.add_argument("--time", dest="time_filter", choices=("hour", "day", "week", "month", "year", "all"))
    parser.add_argument("--subreddit", help="Optional subreddit name to search inside.")
    parser.add_argument("--sleep", dest="sleep_seconds", type=float, help="Pause before saving next story.")
    parser.add_argument("--user-agent", help="HTTP/API User-Agent sent to Reddit.")
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
        return copy.deepcopy(DEFAULT_CONFIG)

    try:
        user_config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Config file {path} contains invalid JSON: {exc}") from exc

    if not isinstance(user_config, dict):
        raise RuntimeError(f"Config file {path} must contain a JSON object.")

    return deep_merge(copy.deepcopy(DEFAULT_CONFIG), user_config)


def save_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


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


def build_query(keywords: Iterable[str], *, allow_prompt: bool = False) -> str:
    words = [str(word).strip() for word in keywords if str(word).strip()]
    if not words and allow_prompt:
        entered = input("Enter keywords separated by spaces: ").strip()
        words = entered.split()
    if not words:
        raise RuntimeError("Specify at least one keyword in config.json or launch arguments.")
    return " ".join(words)


def configured_reddit_login(reddit_config: dict[str, Any]) -> bool:
    required = ("client_id", "client_secret", "username", "password")
    return all(str(reddit_config.get(key, "")).strip() for key in required)


def configured_access_token(reddit_config: dict[str, Any]) -> bool:
    return bool(str(reddit_config.get("access_token", "")).strip())


def configured_cookie(reddit_config: dict[str, Any]) -> bool:
    return bool(str(reddit_config.get("cookie", "")).strip())


def bearer_value(value: str) -> str:
    token = value.strip()
    if token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"


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
        raise RuntimeError(f"Reddit OAuth returned HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not connect to Reddit OAuth: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Reddit OAuth returned a non-JSON response.") from exc

    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError(f"Reddit OAuth did not return access_token: {payload}")
    return str(access_token)


def fetch_reddit_posts_with_access_token(config: dict[str, Any], query: str, limit: int) -> list[dict[str, Any]]:
    access_token = str(config["reddit"].get("access_token", "")).strip()
    return fetch_reddit_posts_oauth(config, query, limit, access_token=access_token)


def fetch_reddit_posts_oauth(
    config: dict[str, Any],
    query: str,
    limit: int,
    *,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    reddit_config = config["reddit"]
    search_config = config["search"]
    access_token = access_token or fetch_reddit_oauth_token(reddit_config)
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
    request = urllib.request.Request(url, headers={"Authorization": bearer_value(access_token), "User-Agent": user_agent})

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Reddit API returned HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not connect to Reddit API: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Reddit API returned a non-JSON response.") from exc

    children = payload.get("data", {}).get("children", [])
    return [child.get("data", {}) for child in children]


def fetch_reddit_posts_cookie(config: dict[str, Any], query: str, limit: int) -> list[dict[str, Any]]:
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
    cookie = str(reddit_config.get("cookie") or "").strip()
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Cookie": cookie,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            raise PublicRedditSearchBlockedError(
                "Reddit не принял cookie и вернул 403 Blocked. "
                "Проверьте, что cookie скопированы полностью из авторизованной сессии Reddit, "
                "или попробуйте Bearer token."
            ) from exc
        raise RuntimeError(f"Reddit returned HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not connect to Reddit: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Reddit returned a non-JSON response.") from exc

    children = payload.get("data", {}).get("children", [])
    return [child.get("data", {}) for child in children]


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
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            raise PublicRedditSearchBlockedError(
                "Reddit заблокировал публичный поиск без авторизации. "
                "Заполните блок Reddit API: client_id, client_secret, username, password и user_agent. "
                "Для этого нужен Reddit app типа script на странице https://www.reddit.com/prefs/apps"
            ) from exc
        raise RuntimeError(f"Reddit returned HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not connect to Reddit: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Reddit returned a non-JSON response.") from exc

    children = payload.get("data", {}).get("children", [])
    return [child.get("data", {}) for child in children]


def fetch_reddit_posts(config: dict[str, Any], query: str, *, log: LogCallback | None = None) -> list[dict[str, Any]]:
    reddit_config = config["reddit"]
    search_config = config["search"]
    limit = max(1, min(int(search_config["limit"]), 100))

    if configured_access_token(reddit_config):
        if log:
            log("Using Bearer token from settings.")
        return fetch_reddit_posts_with_access_token(config, query, limit)

    if configured_cookie(reddit_config):
        if log:
            log("Using Reddit cookies from settings.")
        return fetch_reddit_posts_cookie(config, query, limit)

    if configured_reddit_login(reddit_config):
        if log:
            log("Using Reddit OAuth credentials from config.")
        return fetch_reddit_posts_oauth(config, query, limit)

    if log:
        log("Reddit credentials are empty. Using public JSON search.")
    return fetch_reddit_posts_public(config, query, limit)


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
    path = output_dir / f"{safe_filename(title)}_{reddit_id}.txt"

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


def reddit_url_for_post(post: dict[str, Any]) -> str:
    permalink = post.get("permalink") or ""
    return f"https://www.reddit.com{permalink}" if permalink else str(post.get("url") or "")


def run_search(
    config: dict[str, Any],
    *,
    log: LogCallback | None = None,
    progress: ProgressCallback | None = None,
    result: ResultCallback | None = None,
    should_stop: StopCallback | None = None,
) -> dict[str, Any]:
    search_config = config["search"]
    saving_config = config["saving"]
    query = build_query(search_config.get("keywords", []))
    output_dir = Path(str(saving_config["output_dir"])).expanduser()
    min_chars = int(saving_config["min_chars"])
    max_chars = int(saving_config["max_chars"])
    sleep_seconds = float(saving_config["sleep_seconds"])
    skip_nsfw = bool(saving_config.get("skip_nsfw", True))
    existing_ids, existing_hashes = load_existing_signatures(output_dir)

    if log:
        log(f"Searching Reddit for: {query!r}")
    posts = fetch_reddit_posts(config, query, log=log)
    total = len(posts)
    if log:
        log(f"Received posts: {total}")
    if progress:
        progress(0, total)

    saved = 0
    skipped = 0
    results: list[dict[str, Any]] = []

    for index, post in enumerate(posts, start=1):
        if should_stop and should_stop():
            if log:
                log("Search stopped by user.")
            break

        title = post.get("title") or "Untitled"
        reddit_id = str(post.get("id") or "")
        text = normalize_story_text(post.get("selftext") or "")
        item = {
            "title": title,
            "subreddit": post.get("subreddit", "unknown"),
            "url": reddit_url_for_post(post),
            "chars": len(text),
            "status": "skipped",
            "path": "",
        }

        if not is_self_text_post(post, skip_nsfw):
            item["status"] = "skipped: not text or NSFW"
            skipped += 1
        elif len(text) < min_chars:
            item["status"] = f"skipped: shorter than {min_chars}"
            skipped += 1
        else:
            if max_chars > 0 and len(text) > max_chars:
                text = text[:max_chars].rstrip() + "\n\n[Story truncated by saving.max_chars]"
                item["chars"] = len(text)

            content_hash = story_hash(title, text)
            if reddit_id in existing_ids or content_hash in existing_hashes:
                item["status"] = "skipped: duplicate"
                skipped += 1
            else:
                path = save_story(output_dir, post, text, content_hash)
                existing_ids.add(reddit_id)
                existing_hashes.add(content_hash)
                item["status"] = "saved"
                item["path"] = str(path)
                saved += 1
                if log:
                    log(f"Saved: {path}")
                time.sleep(max(0.0, sleep_seconds))

        results.append(item)
        if result:
            result(item)
        if progress:
            progress(index, total)

    summary = {
        "saved": saved,
        "skipped": skipped,
        "total": total,
        "output_dir": str(output_dir.resolve()),
        "results": results,
    }
    if log:
        log(f"Done. Saved: {saved}. Skipped: {skipped}. Folder: {output_dir.resolve()}")
    return summary


def main() -> int:
    args = parse_args()
    try:
        config = apply_cli_overrides(load_config(Path(args.config)), args)
        summary = run_search(config, log=print)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        textwrap.dedent(
            f"""
            Done.
            Saved new stories: {summary['saved']}
            Skipped posts: {summary['skipped']}
            Folder: {summary['output_dir']}
            """
        ).strip()
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
