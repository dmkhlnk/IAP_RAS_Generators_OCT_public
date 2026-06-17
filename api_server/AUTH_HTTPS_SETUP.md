# Настройка аутентификации и HTTPS для API сервера

## Обзор

API сервер теперь поддерживает:
- **Аутентификацию по логину/паролю** (как в панели 3x-ui)
- **HTTPS подключение** для безопасного удалённого доступа
- **Сессионную авторизацию** через cookies

## Быстрый старт

### 1. Настройка логина и пароля

Отредактируйте файл `.env` в корне репозитория:

```bash
cd /path/to/OCT_Generators_IAP_RAS
nano .env
```

Добавьте или обновите следующие строки:

```env
AUTH_ENABLED=true
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password_here
```

**Важно:** Если `ADMIN_PASSWORD` не установлен, при первом запуске будет сгенерирован случайный пароль (он будет показан в консоли).

### 2. Генерация SSL сертификата (для HTTPS)

Для включения HTTPS необходимо создать SSL сертификат:

```bash
cd api_server
python3 generate_ssl_cert.py
```

Это создаст два файла:
- `server.key` - приватный ключ
- `server.crt` - сертификат

**Примечание:** Это самоподписанный сертификат. Браузеры будут показывать предупреждение о безопасности. Для продакшена используйте Let's Encrypt или сертификат от доверенного CA.

### 3. Запуск сервера с HTTPS

#### Вариант 1: Использование скрипта START_SERVER.sh

```bash
./api_server/START_SERVER.sh
```

Скрипт автоматически обнаружит SSL сертификаты и включит HTTPS, если они присутствуют.

#### Вариант 2: Ручной запуск

```bash
cd api_server
python3 api_server.py \
    --host 0.0.0.0 \
    --port 8000 \
    --ssl-keyfile server.key \
    --ssl-certfile server.crt
```

#### Вариант 3: Использование переменных окружения

Добавьте в `.env`:

```env
SSL_KEYFILE=api_server/server.key
SSL_CERTFILE=api_server/server.crt
```

Затем запустите:

```bash
python3 api_server.py --host 0.0.0.0 --port 8000
```

## Использование

### Доступ к веб-интерфейсу

1. Откройте браузер и перейдите по адресу:
   - HTTP: `http://your-server-ip:8000`
   - HTTPS: `https://your-server-ip:8000`

2. Если включена аутентификация, вы увидите форму входа:
   - Введите логин и пароль из `.env` файла
   - Нажмите "Login"

3. После успешного входа вы попадёте на главную страницу виртуального сканера

### Работа с API

Все API эндпоинты требуют аутентификации (если `AUTH_ENABLED=true`).

#### Пример: Вход через API

```bash
curl -X POST https://your-server:8000/api/auth/login \
  -F "username=admin" \
  -F "password=your_password" \
  -c cookies.txt
```

#### Пример: Использование API после входа

```bash
curl -X POST https://your-server:8000/api/v1/scanner/process \
  -F "file=@scatterers.dat" \
  -b cookies.txt
```

## Отключение аутентификации

Для отключения аутентификации (не рекомендуется для продакшена):

```env
AUTH_ENABLED=false
```

Или при запуске:

```bash
AUTH_ENABLED=false python3 api_server.py
```

## Настройка для продакшена

### 1. Использование Let's Encrypt (рекомендуется)

Для получения бесплатного доверенного SSL сертификата:

```bash
# Установите certbot
sudo apt-get install certbot

# Получите сертификат
sudo certbot certonly --standalone -d your-domain.com

# Используйте полученные сертификаты
python3 api_server.py \
    --ssl-keyfile /etc/letsencrypt/live/your-domain.com/privkey.pem \
    --ssl-certfile /etc/letsencrypt/live/your-domain.com/fullchain.pem
```

### 2. Настройка firewall

Откройте порты для HTTPS:

```bash
sudo ufw allow 8000/tcp
# Или для стандартного HTTPS порта:
sudo ufw allow 443/tcp
```

### 3. Использование nginx как reverse proxy (опционально)

Для использования стандартного порта 443 и дополнительной безопасности:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Безопасность

### Рекомендации:

1. **Используйте сильный пароль** для `ADMIN_PASSWORD`
2. **Включите HTTPS** для удалённого доступа
3. **Ограничьте доступ** через firewall (только необходимые IP)
4. **Регулярно обновляйте** зависимости
5. **Не коммитьте** `.env` файл в git (он уже в `.gitignore`)

### Проверка безопасности:

```bash
# Проверьте, что .env не в git
git check-ignore .env

# Проверьте права доступа на .env
ls -la .env
# Должно быть: -rw------- (только владелец может читать)
```

## Устранение неполадок

### Проблема: "Authentication required" даже после входа

**Решение:** Убедитесь, что cookies включены в браузере и что вы используете HTTPS (или localhost для HTTP).

### Проблема: Браузер показывает предупреждение о сертификате

**Решение:** Это нормально для самоподписанного сертификата. Нажмите "Advanced" → "Proceed to site". Для продакшена используйте Let's Encrypt.

### Проблема: Не могу подключиться по HTTPS

**Решение:**
1. Проверьте, что сертификаты существуют: `ls -la api_server/server.*`
2. Проверьте права доступа: `chmod 600 api_server/server.key`
3. Проверьте firewall: `sudo ufw status`

### Проблема: Забыл пароль

**Решение:** Отредактируйте `.env` файл и установите новый `ADMIN_PASSWORD`, затем перезапустите сервер.

## API эндпоинты

### Аутентификация

- `POST /api/auth/login` - Вход (username, password)
- `POST /api/auth/logout` - Выход
- `GET /api/auth/status` - Проверка статуса аутентификации

### Виртуальный сканер

- `POST /api/v1/scanner/process` - Обработка .dat файла (требует аутентификации)
- `GET /api/v1/scanner/download/{session_id}/{image_type}` - Скачивание результата (требует аутентификации)

### Системные

- `GET /health` - Проверка работоспособности (без аутентификации)
- `GET /` - Веб-интерфейс (требует аутентификации, если включена)

