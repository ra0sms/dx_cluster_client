# DX Cluster Client

[English](README.md) | **Русский**

Клиент telnet DX-кластера для Linux и Windows в духе VE7CC CC User.
Написан на Python с PySide6 (Qt 6).

## Скачать

Готовые сборки лежат на странице [Releases](https://github.com/ra0sms/dx_cluster_client/releases):

- **Linux**: `DXClusterClient-<версия>-x86_64.AppImage`. Сделайте файл исполняемым (`chmod +x`) и запустите.
- **Windows**: `DXClusterClient-<версия>-win64.exe`. Один файл, установка не нужна.

## Возможности

- **Подключение** к telnet DX-кластеру, по умолчанию **RA3CO-2 (`ra3co.com:7373`)**. Вход по
  позывному, ваши команды после входа, поддержание связи и автоматическое переподключение.
- **Споты**: таблица со страной, континентом, диапазоном и видом излучения (CW / SSB / DIGI / FT8).
  Вид берётся из комментария к споту, а если его там нет — по бэнд-плану. Двойной клик открывает
  позывной на QRZ.com.
- **Фильтры** работают в самом клиенте, мгновенно: диапазоны, виды излучения, континент DX,
  континент спотера, страны (только выбранные или все, кроме выбранных). Наборы фильтров можно сохранять.
- **Alarm**: список наблюдения из позывных, масок (`3Y0*`, `*/MM`) или стран целиком, при желании
  с ограничением по диапазонам и видам. Список открывается в отдельном окне. Совпавшие споты попадают
  на отдельную вкладку, звучит звук и появляется системное уведомление.
- **Встроенный telnet-сервер** для логгеров (N1MM, Log4OM, …): подключаетесь к `127.0.0.1:7300`
  и получаете только те споты, что прошли текущие фильтры программы. На `login:` принимается любой
  позывной, поддерживаются `sh/dx [n]` и `bye`. Порт и доступ из локальной сети задаются в настройках.
- **Консоль**: сырой поток кластера и строка команд с историей (`sh/dx 20`, `sh/wwv`, …).
- **Кластеры**: список работающих узлов с [clusters.ra3co.com](https://clusters.ra3co.com/).
  Кэшируется и обновляется раз в час. Можно добавлять свои узлы.
- **Язык**: русский и английский, переключается на лету через меню «Язык».
- **Страны** определяются по `cty.dat` с [country-files.com](https://www.country-files.com/).
  Обновить его можно через «Файл → Обновить cty.dat».

## Запуск из исходников

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m dxclient          # или: dxclusterclient
pytest                      # тесты
```

## Сборка

Готовые файлы складываются в `dist/release/`.

**Linux, AppImage.** Собирайте на старом дистрибутиве: AppImage запускается только на системах,
где версия glibc не старше той, на которой он собран.

```bash
bash packaging/build_appimage.sh   # PYTHON=... — свой интерпретатор, SKIP_PIP=1 — не ставить зависимости
```

**Windows, exe**, на Windows:

```bat
pip install pyside6 pyinstaller
pyinstaller dxclusterclient.spec
```

Или на Linux под Wine в контейнере: `bash packaging/build_windows.sh`.

**GitHub Actions** (`.github/workflows/build.yml`): при пуше тега `v*` собираются AppImage
(на ubuntu-22.04) и exe (на windows-latest), и оба файла прикладываются к релизу на GitHub.

## Где хранятся настройки

- Linux: `~/.config/DXClusterClient/` (`settings.json`, `clusters.json`, обновлённый `cty.dat`)
- Windows: `%APPDATA%\DXClusterClient\`

## Структура проекта

```
dxclient/
  core/      telnet-клиент, парсер спотов, DXCC (cty.dat), диапазоны/виды, фильтры, alarm, список кластеров
  ui/        главное окно и вкладки (PySide6)
  i18n.py    переводы ru/en
  data/      cty.dat, иконка, звук alarm
packaging/   скрипты сборки AppImage / Windows, иконки, .desktop-файл
tests/       тесты (pytest)
```

## Лицензия

[MIT](LICENSE). Входящий в комплект `cty.dat` предоставлен [country-files.com](https://www.country-files.com/).
