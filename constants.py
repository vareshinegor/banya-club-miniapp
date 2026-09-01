# Названия листов Google Таблицы — должны совпадать с реальными вкладками таблицы.
SHEET_USERS = "Пользователи"
SHEET_EVENTS = "Афиша"
SHEET_SIGNUPS = "Записи"
SHEET_MATERIALS = "Материалы"
SHEET_ACHIEVEMENTS = "Достижения"
SHEET_GENERAL = "Общие"

# Заголовки колонок (первая строка каждого листа).
USERS_HEADERS = [
    "telegram_id",
    "username",
    "sb_id",
    "ФИО",
    "Дата рождения",
    "Компания/Проект",
    "Должность",
    "Город",
    "Телефон",
    "Сфера",
    "Роль",
    "Запрос",
    "Предложение",
    "Доход",
    "Как узнал",
    "Статус",
    "Дата регистрации",
]
EVENTS_HEADERS = ["ID", "Название", "Описание", "Дата", "Время", "Место", "Цена", "Фото"]
# "Заказ" — order_id, который мы отправляем в Продамус и получаем обратно в
# вебхуке (там уже как order_num) — по нему находим нужную строку записи.
SIGNUPS_HEADERS = ["telegram_id", "ID события", "Дата записи", "Статус", "Заказ"]
MATERIALS_HEADERS = ["Название", "Описание", "Ссылка", "Категория", "Дата публикации"]
ACHIEVEMENTS_HEADERS = ["telegram_id", "Название", "Описание", "Дата"]
# Сюда сейлбот пишет связку telegram_id -> platform_id ДО того, как человек
# доходит до анкеты. При регистрации platform_id подтягивается отсюда и
# сохраняется как sb_id в листе "Пользователи".
GENERAL_HEADERS = ["telegram_id", "platform_id", "Дата получения"]

# Статус членства. Только "активный" даёт право записываться на мероприятия в Афише.
# Новые анкеты по умолчанию попадают в "неактивный" — админ переключает вручную в таблице
# после проверки анкеты.
STATUS_ACTIVE = "активный"
STATUS_INACTIVE = "неактивный"

SIGNUP_STATUS_PENDING = "ожидает оплаты"
SIGNUP_STATUS_PAID = "оплачено"
SIGNUP_STATUS_FAILED = "отклонено"

# Пошаговая анкета вступления. Единый источник правды: бэкенд отдаёт эту структуру на
# фронтенд (см. /api/auth и /api/onboarding-config), фронтенд просто рендерит шаги по ней.
#
# Типы шагов:
#   text        — одно текстовое поле (может быть multiline)
#   fields      — несколько текстовых полей на одном экране (ключ каждого поля свой)
#   select      — один вариант из списка (может иметь "other" со свободным текстом
#                 и followup — доп. поле, всплывающее при выборе конкретного варианта)
#   multiselect — несколько вариантов из списка
ONBOARDING_STEPS = [
    {
        "key": "fio",
        "type": "text",
        "header": "ФИО",
        "title": "Как тебя представить братьям?",
        "question": "Напиши фамилию, имя и отчество полностью.",
        "placeholder": "Иванов Иван Иванович",
        "required": True,
    },
    {
        "key": "dob",
        "type": "text",
        "header": "Дата рождения",
        "title": "Когда тебя поздравлять с днём рождения?",
        "question": "Укажи дату в формате ДД.ММ.ГГГГ.",
        "placeholder": "14.03.1986",
        "required": True,
    },
    {
        "key": "company_position",
        "type": "fields",
        "title": "Чем ты занимаешься?",
        "question": "Компания, проект и должность. Это будет видно братьям в профиле.",
        "fields": [
            {"key": "company", "header": "Компания/Проект", "label": "Компания / проект", "placeholder": "Ветров и Партнёры", "required": True},
            {"key": "position", "header": "Должность", "label": "Должность", "placeholder": "Управляющий партнёр", "required": False},
        ],
    },
    {
        "key": "contacts",
        "type": "fields",
        "title": "Как с тобой связаться?",
        "question": "Город и телефон — только для связи внутри Ордена.",
        "fields": [
            {"key": "city", "header": "Город", "label": "Город", "placeholder": "Москва", "required": True},
            {"key": "phone", "header": "Телефон", "label": "Телефон", "placeholder": "+7 900 000-00-00", "required": False},
        ],
    },
    {
        "key": "sphere",
        "type": "multiselect",
        "header": "Сфера",
        "title": "Сфера",
        "question": "Можно выбрать несколько. Напиши коротко — это увидят в твоём профиле.",
        "required": True,
        "options": [
            {"value": "construction", "label": "🏗️ Строительство"},
            {"value": "production_trade", "label": "🏭 Производство / Торговля"},
            {"value": "development", "label": "🏢 Девелопмент"},
            {"value": "investments", "label": "📈 Инвестиции"},
            {"value": "it", "label": "💻 IT / Технологии"},
            {"value": "industry", "label": "⚙️ Промышленность"},
            {"value": "finance", "label": "🏦 Финансы"},
            {"value": "logistics", "label": "🚚 Логистика"},
            {"value": "real_estate", "label": "🏠 Недвижимость"},
            {"value": "consulting", "label": "💼 Бизнес-консалтинг"},
            {"value": "foreign_trade", "label": "🌍 ВЭД"},
            {"value": "other", "label": "✏️ Другое"},
        ],
    },
    {
        "key": "role",
        "type": "select",
        "header": "Роль",
        "title": "Твоя роль в бизнесе",
        "question": "Один вариант.",
        "required": True,
        "options": [
            {"value": "owner", "label": "👑 Собственник"},
            {"value": "ceo", "label": "💼 CEO / Гендиректор"},
            {"value": "investor", "label": "💰 Инвестор"},
            {"value": "top_management", "label": "🏆 Топ-менеджмент"},
            {"value": "partner", "label": "🤝 Партнёр"},
            {"value": "other", "label": "✏️ Другое"},
        ],
    },
    {
        "key": "request",
        "type": "multiselect",
        "header": "Запрос",
        "title": "Что ты ищешь в первую очередь?",
        "question": "Можно выбрать несколько.",
        "required": True,
        "options": [
            {"value": "investments", "label": "💸 Инвестиции"},
            {"value": "partners", "label": "🤝 Партнёров"},
            {"value": "clients", "label": "📢 Клиентов"},
            {"value": "contractors", "label": "🔨 Подрядчиков"},
            {"value": "mentorship", "label": "🧠 Экспертизу / Ментора"},
            {"value": "networking", "label": "🔄 Нетворкинг"},
            {"value": "ideas", "label": "💡 Идеи для проектов"},
            {"value": "recharge_space", "label": "🧘 Пространство для отдыха"},
            {"value": "like_minded", "label": "👥 Единомышленников"},
        ],
    },
    {
        "key": "offer",
        "type": "text",
        "header": "Предложение",
        "multiline": True,
        "title": "Что ты можешь дать братьям?",
        "question": "Твой ресурс, экспертиза или возможности.",
        "placeholder": "Например: подряды на промышленных объектах, доступ к СРО, разбор смет",
        "required": True,
    },
    {
        "key": "income",
        "type": "select",
        "header": "Доход",
        "title": "Доход",
        "question": "В месяц. Данные видит только совет Ордена.",
        "required": True,
        "options": [
            {"value": "under_500k", "label": "До 500 000 ₽"},
            {"value": "under_1m", "label": "До 1 000 000 ₽"},
            {"value": "under_3m", "label": "До 3 000 000 ₽"},
            {"value": "over_3m", "label": "Выше 3 000 000 ₽"},
        ],
    },
    {
        "key": "source",
        "type": "select",
        "header": "Как узнал",
        "title": "Как ты узнал о Банном Ордене?",
        "question": "Один вариант.",
        "required": True,
        "options": [
            {
                "value": "recommendation",
                "label": "🙋 По рекомендации",
                "followup": {"key": "referrer", "label": "Имя резидента, который порекомендовал"},
            },
            {"value": "telegram", "label": "📱 Telegram / Tenchat"},
            {"value": "partner_club", "label": "🤝 Партнёрский клуб"},
            {"value": "event", "label": "🔍 Мероприятия"},
            {"value": "personal", "label": "Личное знакомство с основателями"},
            {"value": "other", "label": "✏️ Другое"},
        ],
    },
]
