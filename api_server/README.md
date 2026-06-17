# API Server и Web GUI

Этот каталог содержит API сервер и веб-интерфейс для OCT Generators системы.

## Структура

```
api_server/
├── api_server.py              # Основной API сервер (FastAPI)
├── static/                     # Веб-интерфейс
│   ├── index.html             # Главная страница GUI
│   ├── style.css              # Стили интерфейса
│   └── app.js                 # JavaScript логика
├── api_server.service         # Systemd service файл
├── test_api.py                # Тестовый скрипт для API
├── API_SETUP.md               # Полная документация по настройке
├── QUICK_API_START.md         # Быстрый старт
├── API_IMPLEMENTATION_SUMMARY.md  # Сводка реализации
└── GUI_README.md              # Документация по GUI
```

## Быстрый старт

### 1. Установка зависимостей

После клонирования репозитория перейдите в корневую директорию проекта:

```bash
cd OCT_Generators_IAP_RAS
pip install -r requirements.txt
```

### 2. Настройка аутентификации (для удалённого доступа)

Создайте файл `.env` в корне репозитория (скопируйте из `env.example`):

```bash
cp env.example .env
nano .env
```

Установите логин и пароль:

```env
AUTH_ENABLED=true
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password_here
```

**Важно:** Если пароль не установлен, при первом запуске будет сгенерирован случайный пароль.

### 3. Генерация SSL сертификата (для HTTPS)

Для безопасного удалённого доступа рекомендуется использовать HTTPS:

```bash
cd api_server
python3 generate_ssl_cert.py
```

Это создаст самоподписанный сертификат. Для продакшена используйте Let's Encrypt (см. `AUTH_HTTPS_SETUP.md`).

### 4. Запуск сервера

#### Для удалённого доступа с HTTPS (рекомендуется):

```bash
cd api_server
python3 api_server.py \
    --host 0.0.0.0 \
    --port 8000 \
    --ssl-keyfile server.key \
    --ssl-certfile server.crt \
    --show-ip
```

Или используйте скрипт (автоматически обнаружит SSL сертификаты):

```bash
./api_server/START_SERVER.sh
```

Сервер будет доступен:
- **Локально**: `https://localhost:8000` или `http://127.0.0.1:8000`
- **Удалённо**: `https://<IP-адрес-сервера>:8000` (IP будет показан при запуске)

**Примечание:** Браузер покажет предупреждение о самоподписанном сертификате. Нажмите "Advanced" → "Proceed" для продолжения.

#### Только для локального доступа:

```bash
python3 api_server.py --host 127.0.0.1 --port 8000
```

Сервер будет доступен только с локальной машины:
- `http://localhost:8000` или `http://127.0.0.1:8000`

### 5. Открыть в браузере

**Локальный доступ:**
```
https://localhost:8000  (или http://localhost:8000 если HTTPS не включён)
```

**Удалённый доступ:**
```
https://<IP-адрес-сервера>:8000
```

1. При первом подключении вы увидите форму входа (если включена аутентификация)
2. Введите логин и пароль из `.env` файла
3. После входа вы попадёте на главную страницу виртуального сканера

IP адрес сервера будет показан при запуске с флагом `--show-ip`, или можно узнать командой:
```bash
hostname -I  # Linux
ipconfig getifaddr en0  # macOS
```

## Функциональность

### API Endpoints

- `GET /` - Веб-интерфейс (GUI)
- `GET /health` - Проверка работоспособности
- `POST /api/v1/scanner/process` - Обработка .dat файла
- `GET /api/v1/scanner/download/{session_id}/{image_type}` - Скачивание результата
- `GET /docs` - Автоматическая документация Swagger UI

### Веб-интерфейс

- Современный дизайн с градиентами
- Drag & Drop загрузка файлов
- Визуальная обратная связь
- Автоматическое отображение результатов
- Скачивание сгенерированных изображений

## Запуск как сервис

```bash
# Отредактировать пути в api_server.service если нужно
sudo cp api_server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable api_server
sudo systemctl start api_server
```

## Важно

- API сервер использует `Configuration.ini` из корня репозитория
- API сервер использует `virtual_scanner.py` из корня репозитория
- API и GUI - это дополнительный слой, не заменяют существующий функционал

## Безопасность

API сервер поддерживает:
- ✅ **Аутентификацию по логину/паролю** (сессионная через cookies)
- ✅ **HTTPS подключение** для безопасного удалённого доступа
- ✅ **Защиту всех API эндпоинтов** (кроме `/health` и `/api/auth/*`)

Подробная документация: `AUTH_HTTPS_SETUP.md`

## Документация

- `QUICK_API_START.md` - Быстрый старт
- `API_SETUP.md` - Полная документация по API
- `AUTH_HTTPS_SETUP.md` - Настройка аутентификации и HTTPS
- `GUI_README.md` - Документация по веб-интерфейсу

