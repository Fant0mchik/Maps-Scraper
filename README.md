# 📍 Google Maps Collector CLI

This project is a dual-language guide for using the Google Maps Company Collector via the command line interface.

---

## 🇬🇧 English

### 📌 Description
`parser.py` is a command-line tool to collect information about companies from Google Maps based on keywords and US states.

### ✨ Features:
- 🔄 Asynchronous background data collection (`collect`)
- 📄 Export collected companies to a CSV file (`export`)
- 📋 List companies in terminal (`list`)
- 🧪 Store and deduplicate results in SQLite DB (`companies.db`)

---

### ⚙️ Requirements
- Python 3.8+
- `.env` file with:
  ```env
  GOOGLE_API_KEY=your_api_key_here
  RADIUS_METERS=50000
  REQUEST_DELAY=2.0
  ```
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

---

### 🚀 Usage

#### 1. Start data collection in the background

The task runs in the background and logs are written to <task_id>.log.

```bash
python parser.py collect <keyword> [--state <STATE>]
```

- `<keyword>` — search term (e.g., `logistics`, `transport`)

- `--state` — optional two-letter US state abbreviation (e.g., `NY`, `CA`)

- If `--state` is not provided, it collects from all major cities across all states.

**Example:**

```bash
python parser.py collect logistics --state TX
```

#### 2. List companies in terminal

Returns exacts number of results (without websites).

```bash
python parser.py list [--size <N>] [--skip <M>] [--keyword <KEY>] [--state <STATE>]
```

- `--size` — number of results per page (default: `20`)

- `--skip` — number of pages to skip (default: `0`)

- `--keyword` — filter by search keyword

- `--state` — filter by state

**Example:**

```bash
python parser.py list --keyword logistics --state NY
```

#### 3. Export companies to CSV

Exports collected data to .csv file.

```bash
python parser.py export [--filename <file.csv>] [--size <N>] [--skip <M>] [--keyword <KEY>] [--state <STATE>]
```

- `--filename` — output file name (default: `companies.csv`)
  - Can be exported into a folder: `<directory>\\<filename>.csv` (*example*: `export\\companies.csv`)

- Other parameters are same as in `list`

**Example:**

```bash
python parser.py export --filename tx_logistics.csv --keyword logistics --state TX
```

---

## 🇺🇦 Українська

### 📌 Опис
`parser.py` — це утиліта для збору інформації про компанії з Google Maps за ключовими словами та штатами США.

### ✨ Можливості:
- 🔄 Збір даних у фоні (`collect`)
- 📄 Експорт у CSV-файл (`export`)
- 📋 Вивід у консоль (`list`)
- 🧪 Уникнення дублікатів у базі (`companies.db`)

---

### ⚙️ Вимоги
- Python 3.8+
- `.env` файл з ключем API:
  ```env
  GOOGLE_API_KEY=ваш_ключ
  RADIUS_METERS=50000
  REQUEST_DELAY=2.0
  ```
- Встановлення залежностей:
  ```bash
  pip install -r requirements.txt
  ```

---

### 🚀 Використання

#### 1. Збір даних у фоні

Запуск збору даних без блокування консолі.

```bash
python parser.py collect <keyword> [--state <STATE>]
```

- `<keyword>` — ключове слово для пошуку (наприклад: `logistics`).
- `--state` — необов’язковий параметр зі скороченням штату (наприклад: `NY`, `CA`). Якщо не вказано — збір по всіх штатах.

**Приклад:**

```bash
python parser.py collect logistics --state TX
```

- Після запуску буде виведено Task ID та ім’я лог-файлу (наприклад: `abcd1234.log`).
- Логи роботи можна переглядати в цьому файлі.

#### 2. Вивід списку компаній

Виводить обмежену кількість записів в консоль.

```bash
python parser.py list [--size <N>] [--skip <M>] [--keyword <KEY>] [--state <STATE>]
```

- `--size` — кількість записів на сторінку (за замовчуванням `20`).
- `--skip` — номер сторінки (за замовчуванням `0`).
- `--keyword` — фільтр по ключевому слову.
- `--state` — фільтр по штату.

**Приклад:**

```bash
python parser.py list --keyword logistics --state NY
```

#### 3. Експорт у CSV

Експортує зібрані дані у файл CSV.

```bash
python parser.py export [--filename <file.csv>] [--size <N>] [--skip <M>] [--keyword <KEY>] [--state <STATE>]
```

- `--filename` — ім’я вихідного файлу (за замовчуванням `companies.csv`).
- `--size`, `--skip`, `--keyword`, `--state` — такі ж опції, як у `list`.

**Приклад:**

```bash
python parser.py export --filename tx_logistics.csv --keyword logistics --state TX
```

---
