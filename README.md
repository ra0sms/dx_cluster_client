# DX Cluster Client

Клиент DX-кластера для Linux и Windows в духе VE7CC CC User. Python + PySide6 (Qt 6).

## Возможности

- Подключение к telnet DX-кластеру (по умолчанию **RA3CO-2, `ra3co.com:7373`**), автоматический вход
  по позывному, команды после входа, keepalive, автоматическое переподключение.
- **Споты**: таблица со страной, континентом, диапазоном и видом излучения (CW / SSB / DIGI / FT8 —
  из комментария, иначе по бэнд-плану). Двойной клик — поиск позывного на QRZ.com.
- **Фильтры** (на стороне клиента, мгновенно): диапазоны, виды излучения, континент DX,
  континент спотера, страны (только выбранные / кроме выбранных), сохраняемые наборы фильтров.
- **Alarm**: список наблюдения — позывные, маски (`3Y0*`, `*/MM`) или страны целиком,
  с ограничением по диапазонам и видам. Отдельная таблица совпадений, звук, системное уведомление.
- **Консоль**: сырой поток кластера и строка команд (`sh/dx 20`, `sh/wwv`, …) с историей.
- **Кластеры**: список работающих узлов с [clusters.ra3co.com](https://clusters.ra3co.com/)
  (`clusters.json`, кэшируется, обновляется раз в час) плюс собственные узлы.
- Интерфейс на русском и английском, переключается на лету (меню «Язык»).
- Страны — по `cty.dat` с [country-files.com](https://www.country-files.com/), обновляется из меню «Файл».

## Запуск из исходников

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m dxclient          # или: dxclusterclient
pytest                      # тесты ядра
```

## Сборка дистрибутива

```bash
pyinstaller dxclusterclient.spec    # → dist/DXClusterClient(.exe)
```

Сборка под обе ОС также настроена в GitHub Actions (`.github/workflows/build.yml`, по тегу `v*`).

## Где хранятся настройки

- Linux: `~/.config/DXClusterClient/` (`settings.json`, `clusters.json`, обновлённый `cty.dat`)
- Windows: `%APPDATA%\DXClusterClient\`

## Структура

```
dxclient/
  core/      telnet-клиент, парсер спотов, DXCC (cty.dat), диапазоны/виды, фильтры, alarm, список кластеров
  ui/        главное окно и вкладки (PySide6)
  i18n.py    переводы ru/en
  data/      cty.dat, иконка, звук alarm
tests/       тесты ядра (pytest)
```
