# Troubleshooting: Server Access Issues

## ERR_EMPTY_RESPONSE Error

Если вы получаете ошибку `ERR_EMPTY_RESPONSE` при попытке доступа к серверу, проверьте следующее:

### 1. Сервер не запущен

**Проблема:** Сервер не запущен или остановлен.

**Решение:**
```bash
# Запустите сервер
cd api_server
python3 api_server.py --host 0.0.0.0 --port 8000 --show-ip
```

Или используйте скрипт:
```bash
./api_server/START_SERVER.sh
```

### 2. Неправильный IP адрес

**Проблема:** Используется неправильный IP адрес (например, 240.0.0.2).

**Решение:**
Узнайте правильный IP адрес сервера:
```bash
hostname -I  # Linux
# или
python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); print(s.getsockname()[0]); s.close()"
```

**Правильный IP этого сервера:** `5.129.217.250`

Используйте: `http://5.129.217.250:8000`

### 3. Файрвол блокирует доступ

**Проблема:** Файрвол блокирует порт 8000.

**Решение:**
```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 8000/tcp
sudo ufw reload

# CentOS/RHEL (firewalld)
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload

# Проверка
sudo ufw status
# или
sudo firewall-cmd --list-ports
```

### 4. Сервер слушает только на localhost

**Проблема:** Сервер запущен с `--host 127.0.0.1` вместо `--host 0.0.0.0`.

**Решение:**
Запустите сервер с правильным хостом:
```bash
python3 api_server.py --host 0.0.0.0 --port 8000
```

### 5. Проверка доступности сервера

**Локально:**
```bash
curl http://localhost:8000/health
```

**Удалённо:**
```bash
curl http://5.129.217.250:8000/health
```

### 6. Проверка, что сервер запущен

```bash
# Проверка процесса
ps aux | grep api_server

# Проверка порта
netstat -tuln | grep 8000
# или
ss -tuln | grep 8000
```

## Быстрый старт

1. **Запустите сервер:**
   ```bash
   cd api_server
   python3 api_server.py --host 0.0.0.0 --port 8000 --show-ip
   ```

2. **Откройте в браузере:**
   - Локально: `http://localhost:8000`
   - Удалённо: `http://5.129.217.250:8000`

3. **Проверьте health endpoint:**
   ```bash
   curl http://5.129.217.250:8000/health
   ```

## Контакты и поддержка

Если проблема не решена, проверьте логи сервера и убедитесь, что:
- Все зависимости установлены (`pip install -r requirements.txt`)
- Файл `Configuration.ini` существует в корне репозитория
- Файл `virtual_scanner.py` существует в корне репозитория


