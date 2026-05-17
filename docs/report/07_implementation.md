## 4 Реализация

### 4.1 Структура проекта
Код расположен в каталоге `src/` и разделён на уровни:
- `src/core/` — доменные модели и расчёты агрегатов (отчёты, CSV); нет внешних зависимостей;
- `src/infra/db/` — подключение SQLite, схема, репозитории, migration runner;
- `src/infra/security/` — криптография для защиты локальной БД;
- `src/infra/logging.py` — централизованное логирование с ротацией файлов;
- `src/ui_flet/` — UI-слой на Flet: компоненты, тема, экраны.

Точка входа: `main_flet.py` — Material 3 тема, layout, роутинг, диалог пароля,
жизненный цикл шифрования.

### 4.2 Основные сценарии

- **Транзакции**: добавление дохода/расхода, группировка по дате (Сегодня / Вчера / число),
  фильтр по типу и месяцу, поиск по заметке/категории, подтверждение при удалении.
- **Отчёты**: расходы по категориям (горизонтальные ProgressBar-ряды с процентом и суммой);
  столбчатый график расходов по дням с адаптивной шириной столбцов.
- **Обзор**: кастомный двойной столбчатый график доходов и расходов с независимыми
  Y-шкалами для каждой серии; итоговые метрики за период.
- **Цели**: CRUD целей, атомарное пополнение (`deposit()`), кольцевой прогресс-индикатор,
  сводный баннер общего прогресса по всем целям.
- **Напоминания**: CRUD напоминаний, периодичность (none/daily/weekly/monthly),
  отметка выполнения, подсветка просроченных и ближайших (< 3 дней).
- **Категории**: CRUD категорий с типом (доход/расход/оба) и выбором иконки/цвета.
- **Настройки**: смена пароля, статус шифрования, CSV export/import операций.

### 4.3 Хранение данных (SQLite)

Инициализация схемы — в `src/infra/db/schema.py` (`SCHEMA_VERSION = 4`).
Доступ к данным — через репозитории в `src/infra/db/repositories.py`.
Схема включает таблицы: `categories`, `transactions`, `goals`, `reminders`, `settings`.

Ключевые решения:
- `isolation_level=None` (autocommit) — нет скрытых транзакций.
- `journal_mode=DELETE` — нет WAL-файлов, plaintext не утекает при краше.
- `amount_cents: int` — суммы в копейках, никаких float.
- Даты как ISO-8601 `TEXT` — лексикографическая сортировка работает корректно.
- БД работает только в памяти (`conn.deserialize()`) — на диск пишется
  только зашифрованный blob после каждой транзакции.

### 4.4 Migration Runner

`src/infra/db/migrations.py` реализует атомарные миграции схемы:
- каждая миграция — `Migration(from_version, to_version, name, apply)`;
- `apply_pending()` применяет цепочку шагов от текущей до целевой версии;
- каждый шаг выполняется в отдельной транзакции с откатом при ошибке;
- текущая версия хранится в таблице `settings` (ключ `schema_version`).

### 4.5 Защита данных

Шифрование файла БД:
- контейнер AES-GCM (256-бит) аутентифицирует целостность данных;
- ключ получается из пароля через scrypt (n=2¹⁴, r=8, p=1);
- формат контейнера: `MAGIC(4) + salt(16) + nonce(12) + ciphertext`;
- БД существует только в памяти процесса (`connect_in_memory()`);
- атомарная запись: шифрование → `.tmp`-файл → `os.replace()`;
- autosave hook срабатывает после каждого `COMMIT`, финальное сохранение
  выполняется через `atexit` и `on_window_event(CLOSE)`.

### 4.6 Репозиторный слой

| Репозиторий | Ключевые методы |
|------------|----------------|
| `CategoryRepository` | `ensure_defaults()`, `list_all()`, `create()`, `update()`, `delete()` |
| `TransactionRepository` | `create()`, `list_between(tx_type?)`, `list_all()`, `delete()` |
| `GoalRepository` | `create()`, `get()`, `deposit()`, `update()`, `delete()`, `list_all()` |
| `ReminderRepository` | `create()`, `list_due_sorted()`, `mark_done()`, `update()`, `delete()` |

`GoalRepository.deposit()` выполняет атомарный инкремент с ограничением
`MIN(target_cents, current_cents + ?)` на уровне SQL.

### 4.7 UI-слой (Flet)

Каждый экран — чистая функция `build_<screen>(page, repos, navigate, rebuild) → ft.Control`,
возвращающая только контент без сайдбара.

**Layout:** `main_flet.py` управляет `build_sidebar()` + `ft.AnimatedSwitcher(FADE, 160 мс)`.
Смена маршрута обновляет только `content_switcher.content`, сайдбар остаётся стабильным.

**Тема:** Material 3 через `ft.Theme(color_scheme_seed="#22C55E", use_material3=True)`.
Светлая и тёмная темы переключаются без перезапуска.

**Графики:** реализованы на нативных Flet-контролах без сторонних библиотек.
Столбчатый график строится через `ft.Column([spacer, bar, label])` — пропорциональный
отступ сверху задаёт высоту столбца; двойная Y-шкала отображается через `ft.Stack`
с абсолютным позиционированием меток.

**Иконки/цвета:** 20 иконок и 10 цветов доступны при создании и редактировании
категорий, целей и напоминаний. Иконки хранятся как строковые имена (`"HOME_OUTLINED"`),
`resolve_icon()` конвертирует имя в `ft.Icons` enum при рендеринге.

Переиспользуемые компоненты (`src/ui_flet/components.py`):
`build_sidebar`, `screen_header`, `metric_card`, `tx_row`, `empty_state`,
`icon_picker`, `color_picker`, `confirm_dialog`, `date_group_header`,
`open_dialog`, `close_dialog`.

### 4.8 Логирование

`src/infra/logging.py` настраивает `RotatingFileHandler` (1 МБ × 5 файлов)
и `StreamHandler(stderr, WARNING+)`. Уровень задаётся переменной `PF_LOG_LEVEL`.
Каждый модуль получает именованный логгер через `get_logger("pfm.subsystem")`.

### 4.9 Тестирование

| Файл | Что проверяет |
|------|--------------|
| `test_core_reporting.py` | доменная логика агрегаций (totals, by-category, by-day) |
| `test_crypto.py` | шифрование/дешифрование, неверный пароль, битый заголовок |
| `test_infra_db.py` | репозитории, транзакционность, валидации, граничные случаи |
| `test_inmemory_db.py` | in-memory подключение, serialize/deserialize |
| `test_logging.py` | RotatingFileHandler, уровни логирования |
| `test_migrations.py` | migration runner, цепочка версий, откат при ошибке |
| `test_smoke.py` | импорт всех слоёв, инициализация схемы |

CI запускает `ruff` (линтер) + `mypy` (типы) + `pytest` + `pip-audit` (CVE)
на каждый push через GitHub Actions (Linux + Windows).
