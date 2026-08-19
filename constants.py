# Названия листов Google Таблицы — должны совпадать с реальными вкладками таблицы.
SHEET_USERS = "Пользователи"
SHEET_EVENTS = "Афиша"
SHEET_SIGNUPS = "Записи"
SHEET_MATERIALS = "Материалы"
SHEET_ACHIEVEMENTS = "Достижения"

# Заголовки колонок (первая строка каждого листа).
USERS_HEADERS = [
    "telegram_id",
    "username",
    "ФИО",
    "Дата рождения",
    "Компания/Проект",
    "Сфера",
    "Роль",
    "Запрос",
    "Предложение",
    "Как узнал",
    "Статус",
    "Дата регистрации",
]
EVENTS_HEADERS = ["ID", "Название", "Описание", "Дата", "Время", "Место", "Цена", "Фото"]
SIGNUPS_HEADERS = ["telegram_id", "ID события", "Дата записи", "Статус"]
MATERIALS_HEADERS = ["Название", "Описание", "Ссылка", "Категория", "Дата публикации"]
ACHIEVEMENTS_HEADERS = ["telegram_id", "Название", "Описание", "Дата"]

# Статус членства. Только "активный" даёт право записываться на мероприятия в Афише.
# Новые анкеты по умолчанию попадают в "неактивный" — админ переключает вручную в таблице
# после проверки анкеты.
STATUS_ACTIVE = "активный"
STATUS_INACTIVE = "неактивный"

SIGNUP_STATUS_PAID = "оплачено"

# Пошаговая анкета вступления. Единый источник правды: бэкенд отдаёт эту структуру на
# фронтенд (см. /api/auth и /api/onboarding-config), фронтенд просто рендерит шаги по ней.
ONBOARDING_STEPS = [
    {
        "key": "fio",
        "type": "text",
        "title": "Шаг 1. ФИО",
        "question": "Как тебя представить братьям? Напиши фамилию, имя и отчество полностью.",
        "placeholder": "Иванов Иван Иванович",
        "required": True,
    },
    {
        "key": "dob",
        "type": "text",
        "title": "Шаг 2. Дата рождения",
        "question": "Когда тебя поздравлять с днём рождения? Укажи дату в формате ДД.ММ.ГГГГ.",
        "placeholder": "01.01.1990",
        "required": True,
    },
    {
        "key": "company",
        "type": "text",
        "multiline": True,
        "title": "Шаг 3. Компания / Проект",
        "question": "Чем ты занимаешься? Название компании, проекта или направления деятельности, "
        "которым ты управляешь или владеешь.",
        "hint": "Это будет видно братьям в профиле.",
        "placeholder": "ООО «Ромашка», девелопмент",
        "required": True,
    },
    {
        "key": "sphere",
        "type": "multiselect",
        "title": "Шаг 4. Сфера",
        "question": "Сфера деятельности — можно выбрать несколько вариантов.",
        "hint": "Напиши коротко, это увидят братья в твоём профиле.",
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
        "title": "Шаг 5. Роль",
        "question": "Твоя роль в бизнесе.",
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
        "title": "Шаг 6. Запрос",
        "question": "Что ты ищешь в первую очередь? Можно выбрать несколько.",
        "required": True,
        "options": [
            {"value": "investments", "label": "💰 Инвестиции"},
            {"value": "partners", "label": "🤝 Партнёров"},
            {"value": "clients", "label": "🧑‍🤝‍🧑 Клиентов"},
            {"value": "contractors", "label": "🔧 Подрядчиков"},
            {"value": "mentorship", "label": "🎓 Экспертизу / Ментора"},
            {"value": "networking", "label": "🌐 Нетворкинг"},
            {"value": "ideas", "label": "💡 Идеи для проектов"},
            {"value": "recharge_space", "label": "🧘 Пространство для отдыха / перезагрузки"},
            {"value": "like_minded", "label": "👥 Единомышленников"},
        ],
    },
    {
        "key": "offer",
        "type": "text",
        "multiline": True,
        "title": "Шаг 7. Предложение",
        "question": "Что ты можешь дать братьям? Твой ресурс, экспертиза или возможности.",
        "required": True,
    },
    {
        "key": "source",
        "type": "select",
        "title": "Шаг 8. Откуда узнал",
        "question": "Как ты узнал о Банном Ордене?",
        "required": True,
        "options": [
            {
                "value": "recommendation",
                "label": "🙋 По рекомендации",
                "followup": {"key": "referrer", "label": "Имя резидента, который порекомендовал"},
            },
            {"value": "telegram", "label": "✈️ Telegram / Tenchat"},
            {"value": "partner_club", "label": "🤝 Партнёрский клуб"},
            {"value": "event", "label": "🎉 Мероприятия"},
            {"value": "personal", "label": "🧑‍🤝‍🧑 Личное знакомство с основателями"},
            {"value": "other", "label": "✏️ Другое"},
        ],
    },
]
