"""Minimal runtime-switchable translations (en / ru)."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

LANGUAGES = {"ru": "Русский", "en": "English"}

_RU: dict[str, str] = {
    # main window / tabs
    "Spots": "Споты",
    "Alarm": "Alarm",
    "Console": "Консоль",
    "Clusters": "Кластеры",
    "Filters": "Фильтры",
    "File": "Файл",
    "Settings...": "Настройки...",
    "Update cty.dat": "Обновить cty.dat",
    "Quit": "Выход",
    "Language": "Язык",
    "Help": "Справка",
    "About": "О программе",
    "Connect": "Подключиться",
    "Disconnect": "Отключиться",
    "Cluster:": "Кластер:",
    "Clear": "Очистить",
    # states
    "disconnected": "отключено",
    "connecting": "подключение...",
    "connected": "подключено",
    "reconnect_wait": "ожидание переподключения...",
    "Spots: {shown} / {total}": "Споты: {shown} / {total}",
    "Set your callsign in Settings first.": "Сначала укажите свой позывной в настройках.",
    "Invalid cluster address. Use host:port.": "Неверный адрес кластера. Формат: host:port.",
    "Connection error: {msg}": "Ошибка соединения: {msg}",
    "cty.dat updated: {n} entities.": "cty.dat обновлён: {n} территорий.",
    "cty.dat update failed: {msg}": "Ошибка обновления cty.dat: {msg}",
    # spot columns
    "Time": "Время",
    "Freq": "Частота",
    "DX": "DX",
    "Country": "Страна",
    "Cont": "Конт.",
    "Band": "Диап.",
    "Mode": "Вид",
    "Comment": "Комментарий",
    "Spotter": "Спотер",
    "Sp. cont": "К. сп.",
    # spot context menu
    "Open in QRZ.com": "Открыть на QRZ.com",
    "Copy callsign": "Копировать позывной",
    "Add to Alarm": "Добавить в Alarm",
    "Add country to Alarm": "Добавить страну в Alarm",
    "Exclude country": "Исключить страну",
    # filter panel
    "Bands": "Диапазоны",
    "Modes": "Виды излучения",
    "DX continent": "Континент DX",
    "Spotter continent": "Континент спотера",
    "Countries": "Страны",
    "All countries": "Все страны",
    "Only selected": "Только выбранные",
    "Exclude selected": "Кроме выбранных",
    "Select...": "Выбрать...",
    "Selected: {n}": "Выбрано: {n}",
    "All": "Все",
    "all": "все",
    "none": "нет",
    "None": "Нет",
    "Other bands (VHF+, unknown)": "Прочие диапазоны (УКВ, неизвестные)",
    "Preset": "Набор",
    "Save": "Сохранить",
    "Delete": "Удалить",
    "Preset name:": "Имя набора:",
    "Save filter preset": "Сохранить набор фильтров",
    "Search...": "Поиск...",
    "Select countries": "Выбор стран",
    "Check visible": "Отметить видимые",
    "Uncheck visible": "Снять видимые",
    "PHONE": "SSB/AM/FM",
    "DIGI": "DIGI",
    # alarm tab
    "Watch list": "Список наблюдения",
    "Watch list ({n})...": "Список наблюдения ({n})...",
    "Close": "Закрыть",
    "Matches": "Совпадения",
    "Pattern": "Позывной / маска",
    "Type": "Тип",
    "Note": "Заметка",
    "On": "Вкл",
    "Callsign": "Позывной",
    "Add...": "Добавить...",
    "Edit...": "Изменить...",
    "Remove": "Удалить",
    "Sound": "Звук",
    "Popup": "Уведомление",
    "Alarm entry": "Запись Alarm",
    "Callsign or mask (* and ? allowed), e.g. 3Y0J, VP8*, */MM":
        "Позывной или маска (* и ?), например 3Y0J, VP8*, */MM",
    "Any band": "Любой диапазон",
    "Any mode": "Любой вид",
    "any": "любой",
    "Enabled": "Включено",
    "ALARM: {dx} {freq} {band} {mode}": "ALARM: {dx} {freq} {band} {mode}",
    "Matched": "Совпало",
    # console
    "Command (e.g. sh/dx 20, sh/wwv)": "Команда (например sh/dx 20, sh/wwv)",
    "Send": "Отправить",
    # clusters tab
    "Name": "Имя",
    "Address": "Адрес",
    "Region": "Регион",
    "Status": "Статус",
    "Spots/min": "Спотов/мин",
    "Users": "Польз.",
    "Uptime 7d": "Аптайм 7д",
    "Only working": "Только работающие",
    "All regions": "Все регионы",
    "Refresh list": "Обновить список",
    "Add custom...": "Добавить свой...",
    "Remove custom": "Удалить свой",
    "up": "работает",
    "down": "не работает",
    "custom": "свой",
    "skimmer": "скиммер",
    "cluster": "кластер",
    "Loading cluster list...": "Загрузка списка кластеров...",
    "Loaded {n} nodes ({up} up), updated {when}.": "Загружено узлов: {n} (работают: {up}), обновлено {when}.",
    "Failed to load cluster list: {msg}": "Не удалось загрузить список кластеров: {msg}",
    "Add cluster": "Добавить кластер",
    "Host:": "Хост:",
    "Port:": "Порт:",
    "Name:": "Имя:",
    # settings
    "Settings": "Настройки",
    "Your callsign:": "Ваш позывной:",
    "Password (if required):": "Пароль (если нужен):",
    "Commands after login (one per line):": "Команды после входа (по одной в строке):",
    "Connect on startup": "Подключаться при запуске",
    "Reconnect automatically": "Переподключаться автоматически",
    "Max spots in table:": "Макс. спотов в таблице:",
    "Repeat alarm after (min):": "Повтор Alarm через (мин):",
    "Callsign lookup URL ({call}):": "URL поиска позывного ({call}):",
    "Language:": "Язык:",
    "General": "Общие",
    "Built-in telnet server (filtered spots for logging programs)":
        "Встроенный telnet-сервер (отфильтрованные споты для логгеров)",
    "Server port:": "Порт сервера:",
    "Allow connections from the local network (not only 127.0.0.1)":
        "Разрешить подключения из локальной сети (не только 127.0.0.1)",
    "Telnet server error: {msg}": "Ошибка telnet-сервера: {msg}",
    "Telnet {addr}: {n} clients": "Telnet {addr}: клиентов {n}",
    "Telnet: port {port} unavailable": "Telnet: порт {port} занят",
    "DX cluster client for Linux and Windows.": "Клиент DX-кластера для Linux и Windows.",
}

_TABLES = {"ru": _RU, "en": {"PHONE": "SSB/AM/FM"}}


class Translator(QObject):
    language_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.lang = "ru"

    def set_language(self, lang: str) -> None:
        if lang not in _TABLES:
            lang = "en"
        if lang != self.lang:
            self.lang = lang
            self.language_changed.emit(lang)

    def tr(self, text: str, **kw) -> str:
        s = _TABLES[self.lang].get(text, text)
        return s.format(**kw) if kw else s


translator = Translator()


def tr(text: str, **kw) -> str:
    return translator.tr(text, **kw)
