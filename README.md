# Reddit-story-parser

Python script for searching Reddit text stories by keywords and saving every unique story as a separate `.txt` file.

## What it does

- Searches Reddit posts by keywords from `config.json` or command-line arguments.
- Supports Reddit login settings in `config.json` (`client_id`, `client_secret`, `username`, `password`, `user_agent`).
- If login settings are empty, falls back to Reddit's public JSON endpoint without authorization.
- Saves only text posts (`selftext`) with a configurable minimum length.
- Limits saved story text to about 10,000 characters by default.
- Creates one TXT file per story in the selected folder.
- Adds metadata to every file: title, Reddit ID, subreddit, author, date, score, comments, links, and content hash.
- Checks the output folder before saving and skips stories that were already saved by Reddit ID or content hash.

## Quick start on Windows

1. Edit `config.json`: add keywords, Reddit login settings if you want authenticated search, and saving settings.
2. Run `install_dependencies.bat` once.
3. Run `run_parser.bat` whenever you want to start the parser.

## Config

The default `config.json` contains three sections:

```json
{
  "reddit": {
    "client_id": "",
    "client_secret": "",
    "username": "",
    "password": "",
    "user_agent": "RedditStoryParser/1.0 by your_reddit_username"
  },
  "search": {
    "keywords": ["заработок", "история успеха", "разочарование"],
    "subreddit": "",
    "limit": 25,
    "sort": "relevance",
    "time_filter": "all"
  },
  "saving": {
    "output_dir": "stories",
    "min_chars": 1000,
    "max_chars": 10000,
    "sleep_seconds": 1.0,
    "skip_nsfw": true
  }
}
```

### Config fields

- `reddit.client_id`, `reddit.client_secret`, `reddit.username`, `reddit.password` — Reddit API login settings. Leave them empty to use public search without login.
- `reddit.user_agent` — Reddit requires a descriptive User-Agent. Replace `your_reddit_username` with your Reddit username.
- `search.keywords` — words and phrases for search.
- `search.subreddit` — subreddit name, for example `Entrepreneur`; leave empty to search all Reddit.
- `search.limit` — maximum number of posts to request, capped at 100 by the script.
- `search.sort` — one of `relevance`, `hot`, `top`, `new`, `comments`.
- `search.time_filter` — one of `hour`, `day`, `week`, `month`, `year`, `all`.
- `saving.output_dir` — folder where `.txt` files are saved.
- `saving.min_chars` — skip stories shorter than this value.
- `saving.max_chars` — trim stories longer than this value. Use `0` to disable trimming.
- `saving.sleep_seconds` — pause between saved stories.
- `saving.skip_nsfw` — skip NSFW posts when `true`.

## Command-line usage

Run with settings from `config.json`:

```bash
python reddit_story_parser.py
```

Override keywords from the command line:

```bash
python reddit_story_parser.py заработок успех разочарование
```

Use a different config file:

```bash
python reddit_story_parser.py --config my_config.json
```

Override individual config values:

```bash
python reddit_story_parser.py "side hustle" success failure \
  --output-dir stories \
  --limit 50 \
  --min-chars 1000 \
  --max-chars 10000 \
  --sort relevance \
  --time all
```

Search inside a specific subreddit:

```bash
python reddit_story_parser.py business success --subreddit Entrepreneur
```

Show all options:

```bash
python reddit_story_parser.py --help
```

## Dependencies

All dependencies are listed in `requirements.txt`. At the moment, the parser uses only the Python standard library, so the file contains comments and is still safe to run through `pip install -r requirements.txt`.

## Output format

Each story is saved as one `.txt` file. Example metadata at the top of a saved file:

```txt
Title: Example Reddit story title
Reddit ID: abc123
Content hash: ...
Subreddit: r/AskReddit
Author: u/example_user
Created: 2026-05-12 10:00:00 UTC
Score: 123
Comments: 45
Reddit URL: https://www.reddit.com/r/...
Original URL: https://www.reddit.com/r/...
Saved at: 2026-05-12 10:05:00 UTC

--- STORY ---
Story text...
```

## Notes

If Reddit rate-limits requests, reduce `search.limit`, increase `saving.sleep_seconds`, or try again later. For more stable access, create a Reddit script app and fill the login fields in `config.json`.
