(() => {
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  const devId = new URLSearchParams(window.location.search).get("dev_id");
  const authQuery = window.DEV_MODE && devId ? `?dev_id=${encodeURIComponent(devId)}` : "";

  const screens = {
    loading: document.getElementById("screen-loading"),
    onboarding: document.getElementById("screen-onboarding"),
    main: document.getElementById("screen-main"),
    eventDetail: document.getElementById("screen-event-detail"),
  };

  const state = {
    activeTab: null,
    onboardingSteps: [],
    onboardingIndex: 0,
    onboardingAnswers: {},
  };

  function showScreen(name) {
    Object.entries(screens).forEach(([key, el]) => {
      el.hidden = key !== name;
    });
  }

  async function api(path, options = {}) {
    const res = await fetch(`/api${path}`, {
      method: options.method || "GET",
      headers: { "Content-Type": "application/json" },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    let data = {};
    try {
      data = await res.json();
    } catch (e) {
      data = {};
    }
    if (!res.ok) {
      throw new Error(data.error || `request_failed_${res.status}`);
    }
    return data;
  }

  function escapeHtml(str) {
    return String(str ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c]));
  }

  // --- Инициализация -----------------------------------------------------

  async function init() {
    showScreen("loading");
    try {
      const initData = tg ? tg.initData : "";
      const result = await api(`/auth${authQuery}`, { method: "POST", body: { initData } });
      handleAuthResult(result);
    } catch (err) {
      renderFatalError();
    }
  }

  function handleAuthResult(result) {
    if (result.status === "new") {
      state.onboardingSteps = result.steps || [];
      state.onboardingIndex = 0;
      state.onboardingAnswers = {};
      showScreen("onboarding");
      renderWizardStep();
    } else if (result.status === "active") {
      showScreen("main");
      switchTab("home");
    }
  }

  function renderFatalError() {
    screens.loading.innerHTML = `<p class="muted">Не удалось загрузить приложение.<br>Откройте мини-апп через Telegram.</p>`;
    showScreen("loading");
  }

  // --- Анкета: пошаговый визард ------------------------------------------

  function renderWizardStep() {
    const step = state.onboardingSteps[state.onboardingIndex];
    const total = state.onboardingSteps.length;
    document.getElementById("wizard-progress").textContent = `Шаг ${state.onboardingIndex + 1} из ${total}`;

    const answers = state.onboardingAnswers;
    let html = `<h1 class="wizard-title">${escapeHtml(step.title)}</h1><p class="wizard-question">${escapeHtml(step.question)}</p>`;
    if (step.hint) html += `<p class="wizard-hint">${escapeHtml(step.hint)}</p>`;

    if (step.type === "text") {
      const value = answers[step.key] || "";
      html += step.multiline
        ? `<textarea id="wizard-input" placeholder="${escapeHtml(step.placeholder || "")}">${escapeHtml(value)}</textarea>`
        : `<input type="text" id="wizard-input" placeholder="${escapeHtml(step.placeholder || "")}" value="${escapeHtml(value)}">`;
    } else {
      const isMulti = step.type === "multiselect";
      const selected = isMulti ? answers[step.key] || [] : answers[step.key];

      html += `<div class="wizard-options">`;
      html += step.options
        .map((opt) => {
          const isSelected = isMulti ? selected.includes(opt.value) : selected === opt.value;
          const mark = isMulti ? (isSelected ? "☑" : "☐") : isSelected ? "●" : "○";
          return `<button type="button" class="option-btn${isSelected ? " selected" : ""}" data-value="${escapeHtml(opt.value)}"><span class="option-check">${mark}</span><span>${escapeHtml(opt.label)}</span></button>`;
        })
        .join("");
      html += `</div>`;

      const otherSelected = isMulti ? selected.includes("other") : selected === "other";
      if (otherSelected) {
        const otherValue = answers[`${step.key}_other`] || "";
        html += `<div class="option-other-input"><input type="text" id="wizard-other-input" placeholder="Напишите свой вариант" value="${escapeHtml(otherValue)}"></div>`;
      }

      if (!isMulti) {
        const selectedOpt = step.options.find((o) => o.value === selected);
        if (selectedOpt && selectedOpt.followup) {
          const followupValue = answers[selectedOpt.followup.key] || "";
          html += `<div class="option-other-input"><label>${escapeHtml(selectedOpt.followup.label)}<input type="text" id="wizard-followup-input" data-followup-key="${escapeHtml(selectedOpt.followup.key)}" value="${escapeHtml(followupValue)}"></label></div>`;
        }
      }
    }

    html += `<p class="form-error" id="wizard-error" hidden></p>`;
    html += `<div class="wizard-nav">`;
    if (state.onboardingIndex > 0) {
      html += `<button type="button" class="btn-secondary" id="wizard-back">Назад</button>`;
    }
    html += `<button type="button" class="btn-primary" id="wizard-next">${
      state.onboardingIndex === total - 1 ? "Отправить анкету" : "Далее"
    }</button>`;
    html += `</div>`;

    const container = document.getElementById("wizard-step");
    container.innerHTML = html;

    if (step.type === "select" || step.type === "multiselect") {
      container.querySelectorAll(".option-btn").forEach((btn) => {
        btn.addEventListener("click", () => onOptionClick(step, btn.dataset.value));
      });
    }
    const backBtn = document.getElementById("wizard-back");
    if (backBtn) {
      backBtn.addEventListener("click", () => {
        readCurrentStepIntoState();
        state.onboardingIndex -= 1;
        renderWizardStep();
      });
    }
    document.getElementById("wizard-next").addEventListener("click", onWizardNext);
  }

  function onOptionClick(step, value) {
    if (step.type === "multiselect") {
      const arr = state.onboardingAnswers[step.key] ? [...state.onboardingAnswers[step.key]] : [];
      const idx = arr.indexOf(value);
      if (idx >= 0) arr.splice(idx, 1);
      else arr.push(value);
      state.onboardingAnswers[step.key] = arr;
    } else {
      state.onboardingAnswers[step.key] = value;
    }
    renderWizardStep();
  }

  function readCurrentStepIntoState() {
    const step = state.onboardingSteps[state.onboardingIndex];
    if (step.type === "text") {
      const input = document.getElementById("wizard-input");
      if (input) state.onboardingAnswers[step.key] = input.value.trim();
    } else {
      const otherInput = document.getElementById("wizard-other-input");
      if (otherInput) state.onboardingAnswers[`${step.key}_other`] = otherInput.value.trim();
      const followupInput = document.getElementById("wizard-followup-input");
      if (followupInput) state.onboardingAnswers[followupInput.dataset.followupKey] = followupInput.value.trim();
    }
  }

  function showWizardError(message) {
    const errorEl = document.getElementById("wizard-error");
    errorEl.textContent = message;
    errorEl.hidden = false;
  }

  function validateCurrentStep() {
    const step = state.onboardingSteps[state.onboardingIndex];
    document.getElementById("wizard-error").hidden = true;
    if (!step.required) return true;

    if (step.type === "text") {
      if (!(state.onboardingAnswers[step.key] || "")) {
        showWizardError("Заполните поле, чтобы продолжить");
        return false;
      }
    } else if (step.type === "select") {
      const value = state.onboardingAnswers[step.key];
      if (!value) {
        showWizardError("Выберите один из вариантов");
        return false;
      }
      if (value === "other" && !(state.onboardingAnswers[`${step.key}_other`] || "").trim()) {
        showWizardError("Напишите свой вариант");
        return false;
      }
      const opt = step.options.find((o) => o.value === value);
      if (opt && opt.followup && !(state.onboardingAnswers[opt.followup.key] || "").trim()) {
        showWizardError(`Заполните: ${opt.followup.label}`);
        return false;
      }
    } else if (step.type === "multiselect") {
      const values = state.onboardingAnswers[step.key] || [];
      if (!values.length) {
        showWizardError("Выберите хотя бы один вариант");
        return false;
      }
      if (values.includes("other") && !(state.onboardingAnswers[`${step.key}_other`] || "").trim()) {
        showWizardError("Напишите свой вариант");
        return false;
      }
    }
    return true;
  }

  function buildRegisterPayload() {
    const a = state.onboardingAnswers;
    return {
      fio: a.fio || "",
      dob: a.dob || "",
      company: a.company || "",
      sphere: a.sphere || [],
      sphere_other: a.sphere_other || "",
      role: a.role || "",
      role_other: a.role_other || "",
      request: a.request || [],
      offer: a.offer || "",
      source: a.source || "",
      source_other: a.source_other || "",
      referrer: a.referrer || "",
    };
  }

  async function onWizardNext() {
    readCurrentStepIntoState();
    if (!validateCurrentStep()) return;

    const isLast = state.onboardingIndex === state.onboardingSteps.length - 1;
    if (!isLast) {
      state.onboardingIndex += 1;
      renderWizardStep();
      return;
    }

    const nextBtn = document.getElementById("wizard-next");
    nextBtn.disabled = true;
    nextBtn.textContent = "Отправка…";
    try {
      await api("/register", { method: "POST", body: buildRegisterPayload() });
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      showScreen("main");
      switchTab("home");
    } catch (err) {
      nextBtn.disabled = false;
      nextBtn.textContent = "Отправить анкету";
      showWizardError("Не удалось сохранить анкету. Попробуйте ещё раз.");
    }
  }

  // --- Основное приложение: вкладки -----------------------------------------

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  const tabTitles = {
    home: "Главная",
    events: "Афиша",
    materials: "Материалы",
    profile: "Профиль",
  };

  function switchTab(tab) {
    state.activeTab = tab;
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === tab);
    });
    document.getElementById("topbar-title").textContent = tabTitles[tab];

    const content = document.getElementById("tab-content");
    content.innerHTML = `<div class="empty">Загрузка…</div>`;

    if (tab === "home") loadHome();
    if (tab === "events") loadEvents();
    if (tab === "materials") loadMaterials();
    if (tab === "profile") loadProfile();
  }

  // --- Главная -----------------------------------------------------------

  async function loadHome() {
    const content = document.getElementById("tab-content");
    try {
      const [eventsData, profileData] = await Promise.all([api("/events"), api("/profile")]);
      const nextAny = (eventsData.events || []).slice(0, 1);
      const u = profileData.user;

      content.innerHTML = `
        <div class="card">
          <h3>Привет, ${escapeHtml((u.fio || "участник").split(" ")[0])}! 👋</h3>
          ${u.company ? `<p class="desc">${escapeHtml(u.company)}</p>` : ""}
          ${
            u.is_active
              ? `<span class="badge">Активный участник ✅</span>`
              : `<span class="badge-muted">Анкета на рассмотрении</span>`
          }
        </div>
        ${
          !u.is_active
            ? `<div class="notice">Ваша анкета на проверке у администратора. Как только статус станет «активный», вы сможете записываться на мероприятия.</div>`
            : ""
        }
        <div class="section-title">Ближайшее в афише</div>
        ${nextAny.length ? nextAny.map(renderEventCard).join("") : `<div class="empty">Событий пока нет</div>`}
      `;
      bindEventButtons(content);
      bindEventCards(content);
    } catch (err) {
      content.innerHTML = `<div class="empty">Не удалось загрузить данные</div>`;
    }
  }

  // --- Афиша ---------------------------------------------------------------

  function renderEventCard(e) {
    let actionHtml;
    if (e.is_registered) {
      actionHtml = `<span class="badge">Вы записаны ✅</span>`;
    } else if (e.can_signup) {
      actionHtml = `<button class="btn-small" data-event-id="${e.id}">Записаться</button>`;
    } else {
      actionHtml = `<span class="badge-muted">Только для активных участников</span>`;
    }

    return `
      <div class="card event-card" data-event-card="${e.id}">
        <h3>${escapeHtml(e.title)}</h3>
        <div class="meta">${escapeHtml(e.date)} ${escapeHtml(e.time)} · ${escapeHtml(e.place)}</div>
        <p class="desc">${escapeHtml(e.description)}</p>
        <div class="meta">Стоимость: ${escapeHtml(e.price || "—")}</div>
        <div class="card-actions">
          ${actionHtml}
          <button class="btn-link" data-event-card="${e.id}">Подробнее →</button>
        </div>
      </div>`;
  }

  function bindEventButtons(container) {
    container.querySelectorAll("button[data-event-id]").forEach((btn) => {
      btn.addEventListener("click", (evt) => {
        evt.stopPropagation();
        signupEvent(btn.dataset.eventId, btn);
      });
    });
  }

  function bindEventCards(container) {
    container.querySelectorAll("[data-event-card]").forEach((el) => {
      el.addEventListener("click", (evt) => {
        evt.stopPropagation();
        openEventDetail(el.dataset.eventCard);
      });
    });
  }

  async function signupEvent(eventId, btn) {
    btn.disabled = true;
    btn.textContent = "Обработка…";
    try {
      await api(`/events/${eventId}/signup`, { method: "POST" });
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      btn.outerHTML = `<span class="badge">Вы записаны ✅</span>`;
    } catch (err) {
      btn.disabled = false;
      btn.textContent = "Записаться";
    }
  }

  async function loadEvents() {
    const content = document.getElementById("tab-content");
    try {
      const data = await api("/events");
      const items = data.events || [];
      content.innerHTML = items.length
        ? items.map(renderEventCard).join("")
        : `<div class="empty">Событий пока нет</div>`;
      bindEventButtons(content);
      bindEventCards(content);
    } catch (err) {
      content.innerHTML = `<div class="empty">Не удалось загрузить афишу</div>`;
    }
  }

  // --- Карточка мероприятия ---------------------------------------------

  document.getElementById("event-detail-back").addEventListener("click", () => {
    showScreen("main");
    if (state.activeTab) switchTab(state.activeTab);
  });

  async function openEventDetail(eventId) {
    const content = document.getElementById("event-detail-content");
    content.innerHTML = `<div class="empty">Загрузка…</div>`;
    showScreen("eventDetail");
    try {
      const data = await api(`/events/${eventId}`);
      renderEventDetail(data);
    } catch (err) {
      content.innerHTML = `<div class="empty">Не удалось загрузить мероприятие</div>`;
    }
  }

  function renderEventDetail(data) {
    const e = data.event;
    const attendees = data.attendees || [];
    const content = document.getElementById("event-detail-content");

    let actionHtml;
    if (e.is_registered) {
      actionHtml = `<span class="badge">Вы записаны ✅</span>`;
    } else if (e.can_signup) {
      actionHtml = `<button class="btn-primary" id="event-detail-signup">Записаться</button>`;
    } else {
      actionHtml = `<span class="badge-muted">Только для активных участников</span>`;
    }

    content.innerHTML = `
      <div class="card">
        <h3>${escapeHtml(e.title)}</h3>
        <div class="meta">${escapeHtml(e.date)} ${escapeHtml(e.time)} · ${escapeHtml(e.place)}</div>
        <div class="meta">Стоимость: ${escapeHtml(e.price || "—")}</div>
        <p class="desc">${escapeHtml(e.description)}</p>
        ${actionHtml}
      </div>
      <div class="section-title">Участники (${data.attendees_count})</div>
      ${
        attendees.length
          ? `<div class="card">${attendees
              .map((a) => `<div class="attendee-row">${escapeHtml(a.fio)}</div>`)
              .join("")}</div>`
          : `<div class="empty">Пока никто не записался — станьте первым!</div>`
      }
    `;

    const signupBtn = document.getElementById("event-detail-signup");
    if (signupBtn) {
      signupBtn.addEventListener("click", async () => {
        signupBtn.disabled = true;
        signupBtn.textContent = "Обработка…";
        try {
          await api(`/events/${e.id}/signup`, { method: "POST" });
          if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
          openEventDetail(e.id);
        } catch (err) {
          signupBtn.disabled = false;
          signupBtn.textContent = "Записаться";
        }
      });
    }
  }

  // --- Материалы -------------------------------------------------------------

  async function loadMaterials() {
    const content = document.getElementById("tab-content");
    try {
      const data = await api("/materials");
      const items = data.materials || [];
      content.innerHTML = items.length
        ? items
            .map(
              (m) => `
        <div class="card">
          <h3>${escapeHtml(m.title)}</h3>
          <div class="meta">${escapeHtml(m.category)} ${m.date ? "· " + escapeHtml(m.date) : ""}</div>
          <p class="desc">${escapeHtml(m.description)}</p>
          ${m.link ? `<a class="material-link" href="#" data-link="${escapeHtml(m.link)}">Открыть материал →</a>` : ""}
        </div>`
            )
            .join("")
        : `<div class="empty">Материалов пока нет</div>`;

      content.querySelectorAll("a[data-link]").forEach((a) => {
        a.addEventListener("click", (e) => {
          e.preventDefault();
          const url = a.dataset.link;
          if (tg && tg.openLink) tg.openLink(url);
          else window.open(url, "_blank");
        });
      });
    } catch (err) {
      content.innerHTML = `<div class="empty">Не удалось загрузить материалы</div>`;
    }
  }

  // --- Профиль ---------------------------------------------------------------

  async function loadProfile() {
    const content = document.getElementById("tab-content");
    try {
      const data = await api("/profile");
      const u = data.user;
      const upcoming = data.upcoming_events || [];
      const past = data.past_events || [];
      const achievements = data.achievements || [];

      content.innerHTML = `
        <div class="section-title">Анкета</div>
        <div class="card">
          <div class="profile-field"><span>ФИО</span><span>${escapeHtml(u.fio)}</span></div>
          <div class="profile-field"><span>Дата рождения</span><span>${escapeHtml(u.dob)}</span></div>
          <div class="profile-field"><span>Компания / Проект</span><span>${escapeHtml(u.company)}</span></div>
          <div class="profile-field"><span>Сфера</span><span>${escapeHtml(u.sphere)}</span></div>
          <div class="profile-field"><span>Роль</span><span>${escapeHtml(u.role)}</span></div>
          <div class="profile-field"><span>Запрос</span><span>${escapeHtml(u.request)}</span></div>
          <div class="profile-field"><span>Предложение</span><span>${escapeHtml(u.offer)}</span></div>
          <div class="profile-field"><span>Откуда узнал</span><span>${escapeHtml(u.source)}</span></div>
          <div class="profile-field"><span>Статус</span><span>${u.is_active ? "Активный ✅" : "На рассмотрении"}</span></div>
        </div>

        <div class="section-title">Посещу</div>
        ${
          upcoming.length
            ? upcoming
                .map(
                  (e) => `
          <div class="card event-card" data-event-card="${e.id}">
            <h3>${escapeHtml(e.title)}</h3>
            <div class="meta">${escapeHtml(e.date)} · ${escapeHtml(e.place)}</div>
          </div>`
                )
                .join("")
            : `<div class="empty">Нет предстоящих мероприятий</div>`
        }

        <div class="section-title">Посетил</div>
        ${
          past.length
            ? past
                .map(
                  (e) => `
          <div class="card event-card" data-event-card="${e.id}">
            <h3>${escapeHtml(e.title)}</h3>
            <div class="meta">${escapeHtml(e.date)} · ${escapeHtml(e.place)}</div>
          </div>`
                )
                .join("")
            : `<div class="empty">Пока ничего не посетили</div>`
        }

        <div class="section-title">Достижения</div>
        ${
          achievements.length
            ? achievements
                .map(
                  (a) => `
          <div class="card">
            <h3>🏆 ${escapeHtml(a.title)}</h3>
            ${a.description ? `<p class="desc">${escapeHtml(a.description)}</p>` : ""}
            <div class="meta">${escapeHtml(a.date)}</div>
          </div>`
                )
                .join("")
            : `<div class="empty">Достижений пока нет</div>`
        }
      `;
      bindEventCards(content);
    } catch (err) {
      content.innerHTML = `<div class="empty">Не удалось загрузить профиль</div>`;
    }
  }

  init();
})();
