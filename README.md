# Reddit Story Parser

Desktop-приложение для Windows, которое ищет текстовые истории на Reddit по ключевым словам и сохраняет каждую уникальную историю в отдельный `.txt` файл.

## Возможности

- поиск по нескольким ключевым словам и фразам;
- поиск по всему Reddit или внутри конкретного subreddit;
- сортировка `relevance`, `hot`, `top`, `new`, `comments`;
- фильтр по времени: час, день, неделя, месяц, год или все время;
- публичный поиск без логина или OAuth-доступ через Reddit API;
- фильтры по минимальной и максимальной длине текста;
- пропуск NSFW;
- проверка дублей по Reddit ID и хэшу текста;
- таблица результатов, прогресс и лог в приложении;
- сохранение настроек пользователя;
- сборка в `.exe` и Windows-инсталлятор через Inno Setup 6.

## Быстрый запуск из исходников

1. Установите Python 3.11 или новее.
2. Установите зависимости:

```bat
install_dependencies.bat
```

3. Запустите приложение:

```bat
run_app.bat
```

CLI-режим сохранен:

```bat
run_cli.bat
```

## Сборка EXE

```bat
build_exe.bat
```

После сборки приложение появится здесь:

```text
dist\RedditStoryParser\RedditStoryParser.exe
```

## Сборка установщика

1. Соберите EXE:

```bat
build_exe.bat
```

2. Установите Inno Setup 6.
3. Запустите:

```bat
build_installer.bat
```

Готовый установщик появится здесь:

```text
installer_output\RedditStoryParserSetup.exe
```

## Настройки

Первый запуск создает пользовательский конфиг:

```text
%APPDATA%\RedditStoryParser\config.json
```

В приложении можно менять:

- ключевые слова;
- subreddit;
- лимит постов;
- сортировку и период поиска;
- папку сохранения;
- минимальную и максимальную длину истории;
- паузу между сохранениями;
- пропуск NSFW;
- Reddit API credentials и User-Agent.

Если Reddit API поля пустые, приложение использует публичный JSON-поиск Reddit без авторизации.

## Формат результата

Каждая история сохраняется как `.txt` файл с метаданными:

```text
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
