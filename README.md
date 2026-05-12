# Reddit-story-parser

`Reddit-story-parser` — это простой Python-скрипт, который ищет текстовые истории на Reddit по ключевым словам и сохраняет каждую найденную уникальную историю в отдельный `.txt`-файл.

Скрипт можно запускать без регистрации приложения Reddit: в этом случае он использует публичный JSON-поиск Reddit. Если вам нужен более стабильный доступ, можно заполнить данные Reddit API в `config.json`.

## Что умеет скрипт

- Ищет посты Reddit по ключевым словам из `config.json` или из команды запуска.
- Может искать по всему Reddit или только внутри одного сабреддита.
- Поддерживает вход через Reddit API: `client_id`, `client_secret`, `username`, `password`, `user_agent`.
- Если данные Reddit API не заполнены, автоматически запускается без авторизации через публичный endpoint Reddit.
- Сохраняет только текстовые посты Reddit, то есть посты с полем `selftext`.
- Пропускает слишком короткие истории по настройке `min_chars`.
- Обрезает слишком длинные истории по настройке `max_chars`.
- Создаёт отдельный `.txt`-файл для каждой истории.
- Добавляет в начало каждого файла служебную информацию: заголовок, Reddit ID, сабреддит, автора, дату, рейтинг, число комментариев, ссылки и хэш текста.
- Проверяет папку сохранения и не сохраняет дубликаты, если история уже была сохранена раньше.

## Самый простой запуск на Windows

1. Установите Python 3, если он ещё не установлен.
   - При установке Python на Windows обязательно включите галочку **Add Python to PATH**.
2. Откройте файл `config.json` в обычном текстовом редакторе, например в Notepad, VS Code или Notepad++.
3. В секции `search` укажите ключевые слова, по которым нужно искать истории.
4. При желании измените папку сохранения, минимальную длину истории и другие настройки в секции `saving`.
5. Один раз запустите файл `install_dependencies.bat`.
6. После этого запускайте `run_parser.bat` каждый раз, когда хотите начать поиск.
7. Готовые истории появятся в папке, указанной в `saving.output_dir`. По умолчанию это папка `stories`.

## Самый простой запуск через командную строку

Откройте терминал или командную строку в папке проекта и выполните:

```bash
python reddit_story_parser.py
```

Скрипт возьмёт настройки из файла `config.json`.

Если хотите указать ключевые слова прямо при запуске, напишите их после имени файла:

```bash
python reddit_story_parser.py заработок успех разочарование
```

В этом случае ключевые слова из команды временно заменят `search.keywords` из `config.json`.

## Как заполнить `config.json`

Файл `config.json` — это главный файл настроек. Он выглядит так:

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
    "keywords": [
      "заработок",
      "история успеха",
      "разочарование"
    ],
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

Важно: в JSON нужно соблюдать кавычки, запятые и скобки. Если после изменения файла скрипт пишет ошибку чтения JSON, чаще всего где-то пропущена запятая или лишняя запятая стоит перед закрывающей скобкой.

### Секция `reddit`: данные Reddit

Эта секция отвечает за подключение к Reddit.

```json
"reddit": {
  "client_id": "",
  "client_secret": "",
  "username": "",
  "password": "",
  "user_agent": "RedditStoryParser/1.0 by your_reddit_username"
}
```

#### Вариант 1: запуск без Reddit API

Для обычного использования можно оставить поля пустыми:

```json
"client_id": "",
"client_secret": "",
"username": "",
"password": ""
```

Так скрипт будет искать через публичный JSON-поиск Reddit. Это самый простой вариант, но Reddit может чаще ограничивать такие запросы.

Поле `user_agent` всё равно лучше заполнить понятным текстом. Например:

```json
"user_agent": "RedditStoryParser/1.0 by my_reddit_name"
```

Замените `my_reddit_name` на свой ник Reddit или любое понятное имя.

#### Вариант 2: запуск с Reddit API

Если хотите более стабильный доступ, создайте приложение Reddit типа **script** и заполните поля:

- `client_id` — ID приложения Reddit.
- `client_secret` — секрет приложения Reddit.
- `username` — ваш логин Reddit.
- `password` — ваш пароль Reddit.
- `user_agent` — описание программы, например `RedditStoryParser/1.0 by my_reddit_name`.

Пример:

```json
"reddit": {
  "client_id": "ВАШ_CLIENT_ID",
  "client_secret": "ВАШ_CLIENT_SECRET",
  "username": "ВАШ_REDDIT_ЛОГИН",
  "password": "ВАШ_REDDIT_ПАРОЛЬ",
  "user_agent": "RedditStoryParser/1.0 by my_reddit_name"
}
```

Если вы не понимаете, что такое `client_id` и `client_secret`, просто оставьте эти поля пустыми и используйте запуск без Reddit API.

### Секция `search`: что и где искать

```json
"search": {
  "keywords": [
    "заработок",
    "история успеха",
    "разочарование"
  ],
  "subreddit": "",
  "limit": 25,
  "sort": "relevance",
  "time_filter": "all"
}
```

- `keywords` — ключевые слова и фразы для поиска.
  - Каждое слово или фразу пишите в кавычках.
  - Между элементами ставьте запятые.
  - Пример: `["startup", "success story", "failed business"]`.
- `subreddit` — сабреддит, внутри которого нужно искать.
  - Если оставить пустую строку `""`, поиск будет идти по всему Reddit.
  - Если нужно искать только в `Entrepreneur`, укажите `"Entrepreneur"` без `r/`.
- `limit` — сколько постов запросить у Reddit.
  - Скрипт ограничивает значение максимумом `100`.
  - Для начала удобно поставить `25` или `50`.
- `sort` — сортировка результатов.
  - Можно использовать: `relevance`, `hot`, `top`, `new`, `comments`.
  - Для обычного поиска лучше оставить `relevance`.
- `time_filter` — период поиска.
  - Можно использовать: `hour`, `day`, `week`, `month`, `year`, `all`.
  - `all` означает искать за всё время.

Пример поиска историй про бизнес по всему Reddit:

```json
"search": {
  "keywords": ["business story", "startup", "failure"],
  "subreddit": "",
  "limit": 50,
  "sort": "relevance",
  "time_filter": "all"
}
```

Пример поиска только внутри сабреддита `Entrepreneur`:

```json
"search": {
  "keywords": ["success story", "side hustle"],
  "subreddit": "Entrepreneur",
  "limit": 50,
  "sort": "top",
  "time_filter": "year"
}
```

### Секция `saving`: как сохранять истории

```json
"saving": {
  "output_dir": "stories",
  "min_chars": 1000,
  "max_chars": 10000,
  "sleep_seconds": 1.0,
  "skip_nsfw": true
}
```

- `output_dir` — папка для сохранения `.txt`-файлов.
  - По умолчанию используется папка `stories`.
  - Если папки нет, скрипт создаст её сам.
- `min_chars` — минимальная длина истории в символах.
  - Например, `1000` означает: не сохранять посты короче 1000 символов.
  - Если хотите сохранять больше коротких постов, поставьте `300` или `500`.
- `max_chars` — максимальная длина сохраняемого текста.
  - Например, `10000` означает: сохранить не больше 10000 символов одной истории.
  - Если поставить `0`, скрипт не будет обрезать длинные истории.
- `sleep_seconds` — пауза между сохранениями в секундах.
  - Это помогает не делать запросы слишком быстро.
  - Если Reddit начинает ограничивать запросы, увеличьте значение, например до `2.0` или `5.0`.
- `skip_nsfw` — пропускать ли NSFW-посты.
  - `true` — пропускать NSFW-посты.
  - `false` — не пропускать NSFW-посты.

## Готовые примеры настроек

### Пример 1: простой поиск по всему Reddit

```json
{
  "reddit": {
    "client_id": "",
    "client_secret": "",
    "username": "",
    "password": "",
    "user_agent": "RedditStoryParser/1.0 by my_reddit_name"
  },
  "search": {
    "keywords": ["success story", "business", "failure"],
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

### Пример 2: поиск популярных постов за год в одном сабреддите

```json
{
  "reddit": {
    "client_id": "",
    "client_secret": "",
    "username": "",
    "password": "",
    "user_agent": "RedditStoryParser/1.0 by my_reddit_name"
  },
  "search": {
    "keywords": ["side hustle", "income"],
    "subreddit": "Entrepreneur",
    "limit": 50,
    "sort": "top",
    "time_filter": "year"
  },
  "saving": {
    "output_dir": "entrepreneur_stories",
    "min_chars": 700,
    "max_chars": 0,
    "sleep_seconds": 2.0,
    "skip_nsfw": true
  }
}
```

## Дополнительные команды

Запустить с настройками из `config.json`:

```bash
python reddit_story_parser.py
```

Запустить с другим config-файлом:

```bash
python reddit_story_parser.py --config my_config.json
```

Указать папку сохранения при запуске:

```bash
python reddit_story_parser.py заработок успех --output-dir stories_ru
```

Указать лимит и минимальную длину истории:

```bash
python reddit_story_parser.py "side hustle" success failure --limit 50 --min-chars 1000
```

Искать внутри конкретного сабреддита:

```bash
python reddit_story_parser.py business success --subreddit Entrepreneur
```

Показать все доступные параметры:

```bash
python reddit_story_parser.py --help
```

## Что будет на выходе

Каждая история сохраняется в отдельный `.txt`-файл. В начале файла будет информация о посте, затем сам текст истории.

Пример:

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

## Частые проблемы

### Скрипт ничего не сохранил

Возможные причины:

- Reddit не нашёл подходящих текстовых постов по вашим ключевым словам.
- Найденные посты были короче, чем `saving.min_chars`.
- Посты были не текстовыми, а ссылками, картинками или видео.
- Посты уже были сохранены раньше, поэтому скрипт пропустил дубликаты.
- Включён `skip_nsfw: true`, а найденные посты помечены как NSFW.

Что попробовать:

- Уменьшите `min_chars`, например до `300`.
- Увеличьте `limit`, например до `50` или `100`.
- Используйте английские ключевые слова, потому что большая часть Reddit на английском.
- Оставьте `subreddit` пустым, чтобы искать по всему Reddit.

### Reddit ограничивает запросы или возвращает ошибку

Попробуйте:

- Уменьшить `search.limit`.
- Увеличить `saving.sleep_seconds`.
- Повторить запуск позже.
- Заполнить данные Reddit API в секции `reddit`.

### Ошибка JSON в `config.json`

Проверьте, что:

- Все строки в двойных кавычках.
- Между элементами списка есть запятые.
- Между полями объекта есть запятые.
- Перед закрывающей `]` или `}` нет лишней запятой.

## Зависимости

Все зависимости указаны в `requirements.txt`. Сейчас скрипт использует только стандартную библиотеку Python, поэтому установка зависимостей безопасна и может ничего дополнительно не установить.

На Windows можно просто запустить:

```bat
install_dependencies.bat
```

Или выполнить вручную:

```bash
python -m pip install -r requirements.txt
```
