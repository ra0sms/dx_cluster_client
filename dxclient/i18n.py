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
    "Age": "Возраст",
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
    "Copy": "Копировать",
    "Copied {n} rows": "Скопировано строк: {n}",
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
    "Sort by name": "Сортировать по имени",
    "Sort rules by name; click again to reverse the order":
        "Сортировать правила по имени; повторное нажатие меняет порядок",
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
    "This rule already exists in the watch list: {pattern}":
        "Такое правило уже есть в списке наблюдения: {pattern}",
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
    "PC clock is off by {n} min (corrected automatically)": "Часы ПК расходятся с кластером на {n} мин (учтено)",
    "Spot ages are computed with the cluster time. Please synchronise the computer clock and time zone.":
        "Возраст спотов считается по времени кластера. Синхронизируйте часы и часовой пояс компьютера.",
    "The settings file was damaged and has been reset. A copy was kept:\n{msg}":
        "Файл настроек был повреждён, настройки сброшены. Копия сохранена:\n{msg}",
    "View": "Вид",
    "h": "ч",
    "Remove Alarm matches older than:": "Удалять совпадения Alarm старше:",
    "Clear all spots and Alarm matches": "Очистить все споты и совпадения Alarm",
    "Remove all spots from the table (Alarm matches are kept)":
        "Удалить все споты из таблицы (совпадения Alarm остаются)",
    "Az": "Аз",
    "km": "км",
    "Spotted {n} times": "Спотов: {n}",
    "Minutes since the spot was reported": "Сколько минут назад был спот",
    "Error": "Ошибка",
    "An unexpected error occurred. Details are saved to the log:\n{path}":
        "Произошла непредвиденная ошибка. Подробности сохранены в журнал:\n{path}",
    "min": "мин",
    "now": "сейчас",
    "m": "м",
    "keep": "не удалять",
    "off": "выкл",
    "no limit": "без ограничения",
    "Connection": "Подключение",
    "Telnet server": "Telnet-сервер",
    "Your QTH locator:": "Ваш QTH-локатор:",
    "Remove spots older than:": "Удалять споты старше:",
    "Older spots are removed; from half of this age they are greyed out.":
        "Более старые споты удаляются; начиная с половины этого срока они показываются серым.",
    "Merge duplicate spots within:": "Объединять повторы в течение:",
    "Repeated spots of a station on the same band and mode are merged into one row.":
        "Повторные споты станции на том же диапазоне и виде объединяются в одну строку.",
    "Alarm and forward only spots newer than:": "Alarm и пересылка только для спотов новее:",
    "Older spots (e.g. from sh/dx after login) are shown, but do not trigger Alarm and are not forwarded by the telnet server.":
        "Более старые споты (например, из sh/dx после входа) показываются, но не вызывают Alarm и не пересылаются telnet-сервером.",
    "Repeat alarm after:": "Повтор Alarm через:",
    "Check for new versions on GitHub once a day": "Проверять новые версии на GitHub раз в день",
    "Update cty.dat automatically when it is older than 30 days":
        "Обновлять cty.dat автоматически, если он старше 30 дней",
    "Send spot": "Дать спот",
    "Send spot...": "Дать спот...",
    "Frequency, kHz:": "Частота, кГц:",
    "Callsign:": "Позывной:",
    "Comment:": "Комментарий:",
    "Enter a frequency inside an amateur band and a callsign.":
        "Укажите частоту в любительском диапазоне и позывной.",
    "Connect to a cluster first.": "Сначала подключитесь к кластеру.",
    "Spot sent: {cmd} (the cluster reply is in the Console)": "Спот отправлен: {cmd} (ответ кластера — в Консоли)",
    "Search callsign or country...": "Поиск позывного или страны...",
    "Check for updates": "Проверить обновления",
    "Open settings and log folder": "Открыть папку настроек и журнала",
    "cty.dat updated: {n} entities, version {ver}.": "cty.dat обновлён: {n} территорий, версия {ver}.",
    "Version {v} is available": "Доступна версия {v}",
    "You have the latest version ({v}).": "У вас последняя версия ({v}).",
    "Could not check for updates: {msg}": "Не удалось проверить обновления: {msg}",
    "Solar data unavailable: {msg}": "Солнечные данные недоступны: {msg}",
    "SFI — solar flux, A / K — geomagnetic indices, SN — sunspot number.":
        "SFI — поток солнечного радиоизлучения, A / K — геомагнитные индексы, SN — число солнечных пятен.",
    "Source: {src}, data time: {upd}, fetched {at}. Updated hourly.":
        "Источник: {src}, время данных: {upd}, загружено в {at}. Обновляется раз в час.",
    "Last update failed: {msg}": "Последнее обновление не удалось: {msg}",
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
