# Quick Start: API Server

## Быстрый запуск API сервера

### 1. Установка зависимостей

После клонирования репозитория перейдите в корневую директорию проекта:

```bash
cd OCT_Generators_IAP_RAS
pip install fastapi uvicorn python-multipart
```

Или установить все зависимости:

```bash
pip install -r requirements.txt
```

### 2. Запуск сервера

#### Для удалённого доступа (рекомендуется):

```bash
python3 api_server.py --host 0.0.0.0 --port 8000 --show-ip
```

Сервер будет доступен:
- **Локально**: `http://localhost:8000` или `http://127.0.0.1:8000`
- **Удалённо**: `http://<IP-адрес-сервера>:8000` (IP будет показан при запуске)

#### Только для локального доступа:

```bash
python3 api_server.py --host 127.0.0.1 --port 8000
```

Сервер будет доступен только с локальной машины.

**Узнать IP адрес сервера:**
```bash
hostname -I  # Linux
ipconfig getifaddr en0  # macOS
```

### 3. Проверка работы

**Локальная проверка:**
```bash
curl http://localhost:8000/health
```

**Удалённая проверка (с другого компьютера):**
```bash
curl http://<IP-адрес-сервера>:8000/health
```

**Использование тестового скрипта:**
```bash
# Локально
python3 test_api.py path/to/scatterers.dat

# На удалённом сервере (укажите IP)
python3 test_api.py path/to/scatterers.dat --server http://<IP-адрес-сервера>:8000
```

### 4. Использование API

#### Загрузка .dat файла и получение OCT-скана:

**Локально:**
```bash
curl -X POST "http://localhost:8000/api/v1/scanner/process" \
  -F "file=@scatterers.dat"
```

**Удалённо:**
```bash
curl -X POST "http://<IP-адрес-сервера>:8000/api/v1/scanner/process" \
  -F "file=@scatterers.dat"
```

Ответ содержит ссылки для скачивания:

```json
{
  "status": "success",
  "session_id": "uuid-here",
  "images": {
    "grayscale": "/api/v1/scanner/download/{session_id}/grayscale",
    "hot": "/api/v1/scanner/download/{session_id}/hot"
  }
}
```

#### Скачивание результата:

**Локально:**
```bash
curl -O "http://localhost:8000/api/v1/scanner/download/{session_id}/grayscale"
```

**Удалённо:**
```bash
curl -O "http://<IP-адрес-сервера>:8000/api/v1/scanner/download/{session_id}/grayscale"
```

### 5. Запуск как сервис (для постоянной работы)

```bash
# Копировать service файл
sudo cp api_server.service /etc/systemd/system/

# Отредактировать пути если нужно
sudo nano /etc/systemd/system/api_server.service

# Запустить сервис
sudo systemctl daemon-reload
sudo systemctl enable api_server
sudo systemctl start api_server

# Проверить статус
sudo systemctl status api_server

# Просмотр логов
sudo journalctl -u api_server -f
```

## Важно

- Существующий код `virtual_scanner.py` **не изменён** - он работает как раньше
- API сервер использует существующую функцию `run_oct_simulation` без изменений
- Все существующие скрипты продолжают работать как раньше
- API сервер - это дополнительный способ доступа, не заменяет существующий функционал

## Документация

Полная документация: см. `API_SETUP.md`

