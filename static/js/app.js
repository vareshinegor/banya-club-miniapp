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
  };
  const onbPhases = {
    intro: document.getElementById("onb-intro"),
    form: document.getElementById("onb-form"),
    sending: document.getElementById("onb-sending"),
    done: document.getElementById("onb-done"),
  };

  const state = {
    user: null,
    tab: "home",
    route: "list", // 'list' | 'event'
    eventId: null,
    allParticipants: false,
    seg: "upcoming",
    materialsCategory: "Все",
    cache: { events: null, profile: null, materials: null },
    onb: { phase: "intro", index: 0, steps: [], answers: {} },
    faqOpen: 0,
    pay: { eventId: null, phase: "form", agree: false },
  };

  const ABOUT_VIDEOS = [
    { id: "founder", src: "/static/media/founder.mp4?v=2", title: "Слово основателя", sub: "Филипп о том, зачем Ордену отбор и почему встречи проходят в бане." },
    { id: "thursday", src: "/static/media/thursday.mp4", title: "Как проходит четверг в Ордене", sub: "Один вечер целиком: круг знакомств, запросы резидентов, свободный пар." },
  ];

  const ABOUT_FAQ = [
    { q: "Как появился Банный Орден?", paras: [
      "В какой-то момент мы поняли, что вокруг нас много полезных знакомств, партнеров и интересных предпринимателей, но при этом мало по-настоящему своих людей, с которыми можно не только обсудить рабочие вопросы и обменяться контактами, но и нормально провести время, поговорить без галстуков, поделиться своим запросом или попросить совета.",
      "Так начал собираться Банный Орден, в который постепенно приходили предприниматели из разных сфер со своим опытом, связями и сильными сторонами. Довольно быстро стало понятно, что вместе все эти возможности работают намного мощнее, чем по отдельности.",
      "Кому-то внутри Ордена помогли найти партнера или надежного подрядчика, кто-то получил поддержку в сложный для бизнеса период, а кто-то пришел просто отдохнуть и в итоге познакомился с людьми, вместе с которыми запустил новый проект.",
    ] },
    { q: "Почему именно баня?", paras: [
      "Нас иногда спрашивают, почему мы выбрали именно баню, а не ресторан, конференцию или привычный бизнес-завтрак, и ответ довольно простой: в бане люди быстрее расслабляются, перестают держаться за должности и регалии, а разговор становится более открытым и живым.",
      "Сначала можно обсуждать компании, рынки и цифры, а через час уже говорить о том, что на самом деле сейчас волнует, где нужна помощь и какой проект давно хочется запустить, но пока не хватает подходящего партнера, контакта или взгляда со стороны.",
      "При этом деловая часть встречи никуда не исчезает, просто здесь не нужно за тридцать секунд презентовать себя незнакомым людям и пытаться произвести правильное впечатление. За вечер участники естественным образом узнают, кто чем занимается, в чем особенно силен, какой запрос решает сейчас и чем сам может быть полезен другим.",
      "Поэтому баня для нас стала не фоном для нетворкинга, а пространством, в котором люди быстрее узнают друг друга настоящими, после чего уже появляются партнерства, совместные проекты, рекомендации и сделки.",
    ] },
    { q: "Как Банный Орден поможет мне решить свой запрос?", paras: [
      "Некоторые бизнес-задачи можно решать месяцами: искать подходящего специалиста, собирать рекомендации, писать незнакомым людям и ждать ответа, а потом случайно выяснить, что нужный человек все это время находился в двух рукопожатиях от тебя.",
      "В Банный Орден входят предприниматели из разных сфер, поэтому почти для каждого запроса находится тот, кто уже проходил похожий путь, может поделиться своим опытом, познакомить с нужным специалистом или подсказать, в каком направлении лучше искать решение.",
      "Чтобы такие связи возникали, важно понимать о человеке не только название его компании и должность, но и то, в чем заключается его главная сила, какой запрос он решает сейчас и чем сам готов поделиться с другими резидентами.",
      "Мы хотим развивать эту систему дальше и помогать участникам точнее находить друг друга под конкретные задачи, формировать партнерства и запускать совместные проекты, потому что сила сообщества определяется не количеством людей в общем чате, а количеством связей, которые действительно работают.",
    ] },
    { q: "Почему нельзя просто прийти к вам в баню?", paras: [
      "В Банный Орден нельзя просто купить билет и автоматически стать резидентом, потому что сначала человек приходит по рекомендации одного из участников, после чего мы знакомимся с ним, узнаем, чем он занимается, зачем хочет присоединиться к сообществу и что может в него привнести.",
      "Это не экзамен на успешность и не соревнование в количестве регалий, ведь среди наших резидентов есть предприниматели с разным масштабом бизнеса. Нам намного важнее то, как человек относится к другим, отвечает ли за свои слова и готов ли не только обращаться за помощью, но и поддерживать других участников своими знаниями, опытом или связями.",
      "Нас объединяет отношение к семье, здоровью, развитию, путешествиям и активной жизни, а еще желание строить сильные проекты, не превращая работу в единственное, что в этой жизни существует.",
      "Отбор нужен нам не для того, чтобы выглядеть закрытыми и важными, а для сохранения доверия и атмосферы, ради которой люди приходят в Орден, знакомятся, начинают общаться и со временем действительно становятся кругом своих.",
    ] },
  ];

  function showScreen(name) {
    Object.entries(screens).forEach(([key, el]) => { el.hidden = key !== name; });
  }
  function showOnbPhase(phase) {
    state.onb.phase = phase;
    Object.entries(onbPhases).forEach(([key, el]) => { el.hidden = key !== phase; });
  }

  async function api(path, options = {}) {
    const res = await fetch(`/api${path}`, {
      method: options.method || "GET",
      headers: { "Content-Type": "application/json" },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    let data = {};
    try { data = await res.json(); } catch (e) { data = {}; }
    if (!res.ok) throw new Error(data.error || `request_failed_${res.status}`);
    return data;
  }

  function escapeHtml(str) {
    return String(str ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function initials(fio) {
    return (fio || "").trim().split(/\s+/).slice(0, 2).map((w) => w[0] || "").join("").toUpperCase();
  }

  function openExternalLink(url) {
    if (tg && tg.openLink) tg.openLink(url);
    else window.open(url, "_blank");
  }

  // --- Даты ------------------------------------------------------------

  const MONTHS_SHORT = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
  const MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
  const MONTHS_NOM = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];
  const WEEKDAYS_SHORT = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];
  const WEEKDAYS_FULL = ["Воскресенье", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"];

  function parseEventDate(str) {
    if (!str) return null;
    let m = str.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
    m = str.match(/^(\d{1,2})\.(\d{1,2})\.(\d{2,4})/);
    if (m) {
      let y = +m[3];
      if (y < 100) y += 2000;
      return new Date(y, +m[2] - 1, +m[1]);
    }
    return null;
  }

  function withDate(e) {
    const d = parseEventDate(e.date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return { ...e, _date: d, _past: d ? d < today : false };
  }

  function byDateAsc(a, b) { return (a._date ? a._date.getTime() : Infinity) - (b._date ? b._date.getTime() : Infinity); }
  function byDateDesc(a, b) { return (b._date ? b._date.getTime() : 0) - (a._date ? a._date.getTime() : 0); }

  function dayLabel(d) { return d ? String(d.getDate()).padStart(2, "0") : "--"; }
  function monthLabelShort(d) { return d ? MONTHS_SHORT[d.getMonth()] : ""; }
  function dateShortLabel(d) { return d ? `${d.getDate()} ${MONTHS_GEN[d.getMonth()]}, ${WEEKDAYS_SHORT[d.getDay()]}` : ""; }
  function whenLabel(d, time) { return d ? `${WEEKDAYS_FULL[d.getDay()]}, ${d.getDate()} ${MONTHS_GEN[d.getMonth()]}${time ? " · " + time : ""}` : time || ""; }
  function monthYearLabel(d) { return `${MONTHS_NOM[d.getMonth()]} ${d.getFullYear()}`; }
  function shortDate(str) { const d = parseEventDate(str); return d ? `${d.getDate()} ${MONTHS_GEN[d.getMonth()]}` : str || ""; }

  // --- Общие блоки разметки ------------------------------------------------

  function pageHeaderHtml(title) {
    const badge = state.user && state.user.is_active
      ? '<span class="badge badge-active">Активный</span>'
      : '<span class="badge badge-moderation">На модерации</span>';
    return `<div class="page-header"><span class="page-title">${escapeHtml(title)}</span>${badge}</div>`;
  }

  function sectionLabelHtml(text, rightHtml) {
    return `<div class="section-label"><span>${escapeHtml(text)}</span>${rightHtml || ""}</div>`;
  }

  function skeletonHtml(n) {
    const heights = [74, 150, 96, 96, 70, 46];
    let html = '<div style="display:grid;gap:14px;padding-top:4px">';
    for (let i = 0; i < n; i++) html += `<div class="skeleton" style="height:${heights[i % heights.length]}px"></div>`;
    return html + "</div>";
  }

  function errorStateHtml() {
    return `<div class="state-error">
      <div class="state-error-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M12 8v5M12 16.5v.5" stroke="#E28371" stroke-width="1.8" stroke-linecap="round"/><circle cx="12" cy="12" r="9" stroke="#E28371" stroke-width="1.6"/></svg></div>
      <div class="state-title">Не удалось загрузить</div>
      <p class="state-text">Проверьте соединение и повторите запрос.</p>
      <button class="btn-primary" data-action="retry" style="width:auto;padding:0 26px;display:inline-flex;align-items:center;justify-content:center;margin-top:18px">Повторить</button>
    </div>`;
  }

  function moderationNoticeHtml() {
    return `<div class="notice-moderation">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12 4.5l8 14H4l8-14z" stroke="#C98A3C" stroke-width="1.6" stroke-linejoin="round"/><path d="M12 10v3.5M12 16v.5" stroke="#C98A3C" stroke-width="1.7" stroke-linecap="round"/></svg>
      <div><div class="title">Заявка на рассмотрении</div><div class="text">Совет Ордена подтверждает резидентство. Запись на бани откроется после решения.</div></div>
    </div>`;
  }

  // --- Состояния кнопки записи ---------------------------------------------

  function eventActionState(e) {
    if (e._past) return e.is_registered ? "attended" : "none";
    if (e.is_registered) return "joined";
    if (e.can_signup) return "join";
    return "locked";
  }

  function eventActionHtml(e, opts) {
    const sticky = !!(opts && opts.sticky);
    const st = eventActionState(e);
    if (st === "joined") return `<div class="state-btn state-joined"><svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3.5 8.5l3 3 6-7" stroke="#8CB169" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>Вы записаны</div>`;
    if (st === "locked") return `<div class="state-btn state-locked"><svg width="15" height="15" viewBox="0 0 16 16" fill="none"><rect x="3" y="7" width="10" height="7" rx="2" stroke="#99A49E" stroke-width="1.5"/><path d="M5.5 7V5.5a2.5 2.5 0 015 0V7" stroke="#99A49E" stroke-width="1.5"/></svg>Только для активных</div>`;
    if (st === "attended") return `<div class="state-btn state-attended">Вы посетили</div>`;
    if (st === "join") {
      const label = sticky && e.price ? `Записаться · ${escapeHtml(e.price)}` : "Записаться";
      return `<button class="state-btn state-join" data-join-id="${e.id}">${label}</button>`;
    }
    return "";
  }

  // --- Данные с кэшем -------------------------------------------------------

  async function getEvents(force) {
    if (!state.cache.events || force) state.cache.events = await api("/events");
    return state.cache.events;
  }
  async function getProfile(force) {
    if (!state.cache.profile || force) state.cache.profile = await api("/profile");
    return state.cache.profile;
  }
  async function getMaterials(force) {
    if (!state.cache.materials || force) state.cache.materials = await api("/materials");
    return state.cache.materials;
  }

  // --- Инициализация --------------------------------------------------------

  async function init() {
    showScreen("loading");
    try {
      const initData = tg ? tg.initData : "";
      const result = await api(`/auth${authQuery}`, { method: "POST", body: { initData } });
      if (result.status === "new") {
        state.onb.steps = result.steps || [];
        state.onb.phase = "intro";
        state.onb.index = 0;
        state.onb.answers = {};
        showScreen("onboarding");
        showOnbPhase("intro");
      } else {
        state.user = result.user;
        showScreen("main");
        switchTab("home");
      }
    } catch (err) {
      screens.loading.innerHTML = `<p style="color:var(--muted);font-size:14px;text-align:center;padding:0 32px">Не удалось загрузить приложение.<br>Откройте мини-апп через Telegram.</p>`;
    }
  }

  // --- Анкета: интро/визард/отправка/готово ----------------------------------

  document.getElementById("onb-start").addEventListener("click", () => {
    state.onb.index = 0;
    showOnbPhase("form");
    renderOnbStep();
  });
  document.getElementById("onb-back").addEventListener("click", () => {
    syncOnbTextInputs();
    if (state.onb.index === 0) { showOnbPhase("intro"); return; }
    state.onb.index -= 1;
    renderOnbStep();
  });
  document.getElementById("onb-footer").addEventListener("click", (e) => {
    if (e.target.closest("#onb-next")) goOnbNext();
  });
  document.getElementById("onb-body").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-onb-pick]");
    if (!btn) return;
    const step = currentOnbStep();
    const value = btn.dataset.onbPick;
    if (step.type === "multiselect") {
      const arr = state.onb.answers[step.key] ? [...state.onb.answers[step.key]] : [];
      const idx = arr.indexOf(value);
      if (idx > -1) arr.splice(idx, 1); else arr.push(value);
      state.onb.answers[step.key] = arr;
    } else {
      state.onb.answers[step.key] = value;
    }
    renderOnbStep();
  });
  document.getElementById("onb-body").addEventListener("input", () => {
    syncOnbTextInputs();
    const nextBtn = document.getElementById("onb-next");
    if (nextBtn) nextBtn.disabled = !isOnbStepValid(currentOnbStep());
  });

  function currentOnbStep() { return state.onb.steps[state.onb.index]; }

  function renderOnbStep() {
    const step = currentOnbStep();
    const total = state.onb.steps.length;
    document.getElementById("onb-counter").textContent = `Шаг ${state.onb.index + 1} из ${total}`;
    document.getElementById("onb-ticks").innerHTML = state.onb.steps
      .map((_, i) => `<span class="${i <= state.onb.index ? "done" : ""}"></span>`)
      .join("");

    const answers = state.onb.answers;
    let html = `<div class="onb-step-title">${escapeHtml(step.title)}</div><p class="onb-step-question">${escapeHtml(step.question)}</p>`;

    if (step.type === "text") {
      const value = answers[step.key] || "";
      html += `<div class="onb-field">${
        step.multiline
          ? `<textarea id="onb-input-${step.key}" placeholder="${escapeHtml(step.placeholder || "")}">${escapeHtml(value)}</textarea>`
          : `<input type="text" id="onb-input-${step.key}" placeholder="${escapeHtml(step.placeholder || "")}" value="${escapeHtml(value)}">`
      }</div>`;
    } else if (step.type === "fields") {
      html += step.fields
        .map((f) => {
          const value = answers[f.key] || "";
          return `<div class="onb-field"><div class="onb-field-label">${escapeHtml(f.label)}</div><input type="text" id="onb-input-${f.key}" placeholder="${escapeHtml(f.placeholder || "")}" value="${escapeHtml(value)}"></div>`;
        })
        .join("");
    } else {
      const isMulti = step.type === "multiselect";
      const selected = isMulti ? answers[step.key] || [] : answers[step.key];
      html += `<div class="onb-options">${step.options
        .map((opt) => {
          const on = isMulti ? selected.includes(opt.value) : selected === opt.value;
          return `<button type="button" class="onb-option${on ? " selected" : ""}" data-onb-pick="${escapeHtml(opt.value)}">${escapeHtml(opt.label)}</button>`;
        })
        .join("")}</div>`;
      if (isMulti) html += `<div class="onb-picked-count">Выбрано: ${(selected || []).length}</div>`;

      const otherOn = isMulti ? (selected || []).includes("other") : selected === "other";
      if (otherOn) {
        const otherVal = answers[`${step.key}_other`] || "";
        html += `<div class="onb-field"><input type="text" id="onb-other-input" placeholder="Напиши свой вариант" value="${escapeHtml(otherVal)}"></div>`;
      }
      if (!isMulti) {
        const selOpt = (step.options || []).find((o) => o.value === selected);
        if (selOpt && selOpt.followup) {
          const fVal = answers[selOpt.followup.key] || "";
          html += `<div class="onb-field"><div class="onb-field-label">${escapeHtml(selOpt.followup.label)}</div><input type="text" id="onb-followup-input" data-followup-key="${escapeHtml(selOpt.followup.key)}" value="${escapeHtml(fVal)}"></div>`;
        }
      }
    }
    document.getElementById("onb-body").innerHTML = html;

    const isLast = state.onb.index === total - 1;
    const label = isLast ? "Отправить заявку" : "Дальше";
    document.getElementById("onb-footer").innerHTML = `<button class="btn-primary" id="onb-next" ${isOnbStepValid(step) ? "" : "disabled"}>${label}</button>`;
  }

  function syncOnbTextInputs() {
    const step = currentOnbStep();
    if (step.type === "text") {
      const el = document.getElementById(`onb-input-${step.key}`);
      if (el) state.onb.answers[step.key] = el.value;
    } else if (step.type === "fields") {
      step.fields.forEach((f) => {
        const el = document.getElementById(`onb-input-${f.key}`);
        if (el) state.onb.answers[f.key] = el.value;
      });
    } else {
      const otherEl = document.getElementById("onb-other-input");
      if (otherEl) state.onb.answers[`${step.key}_other`] = otherEl.value;
      const fEl = document.getElementById("onb-followup-input");
      if (fEl) state.onb.answers[fEl.dataset.followupKey] = fEl.value;
    }
  }

  function isOnbStepValid(step) {
    const a = state.onb.answers;
    if (step.type === "text") return !step.required || !!(a[step.key] || "").trim();
    if (step.type === "fields") return step.fields.every((f) => !f.required || !!(a[f.key] || "").trim());
    if (step.type === "select") {
      if (!step.required) return true;
      const v = a[step.key];
      if (!v) return false;
      if (v === "other" && !(a[`${step.key}_other`] || "").trim()) return false;
      const opt = step.options.find((o) => o.value === v);
      if (opt && opt.followup && !(a[opt.followup.key] || "").trim()) return false;
      return true;
    }
    if (step.type === "multiselect") {
      if (!step.required) return true;
      const vals = a[step.key] || [];
      if (!vals.length) return false;
      if (vals.includes("other") && !(a[`${step.key}_other`] || "").trim()) return false;
      return true;
    }
    return true;
  }

  function resolveOnbLabel(step, value) {
    if (value === "other") return (state.onb.answers[`${step.key}_other`] || "").trim() || "Другое";
    const opt = (step.options || []).find((o) => o.value === value);
    return opt ? opt.label : value;
  }

  function buildRegisterPayload() {
    const a = state.onb.answers;
    return {
      fio: a.fio || "", dob: a.dob || "",
      company: a.company || "", position: a.position || "",
      city: a.city || "", phone: a.phone || "",
      sphere: a.sphere || [], sphere_other: a.sphere_other || "",
      role: a.role || "", role_other: a.role_other || "",
      request: a.request || [],
      offer: a.offer || "",
      income: a.income || "",
      source: a.source || "", source_other: a.source_other || "", referrer: a.referrer || "",
    };
  }

  function renderOnbSummary() {
    const a = state.onb.answers;
    const rows = [];
    state.onb.steps.forEach((step) => {
      if (step.type === "fields") {
        step.fields.forEach((f) => {
          const v = (a[f.key] || "").trim();
          if (v) rows.push({ label: f.label, value: v });
        });
        return;
      }
      let value = "";
      if (step.type === "text") value = (a[step.key] || "").trim();
      else if (step.type === "select") {
        const v = a[step.key];
        if (v) {
          value = resolveOnbLabel(step, v);
          if (v === "recommendation" && a.referrer) value += ` (${a.referrer})`;
        }
      } else if (step.type === "multiselect") {
        value = (a[step.key] || []).map((v) => resolveOnbLabel(step, v)).join(", ");
      }
      if (value) rows.push({ label: step.header || step.title, value });
    });
    document.getElementById("onb-summary").innerHTML = rows
      .map((r) => `<div class="onb-summary-row"><span>${escapeHtml(r.label)}</span><span>${escapeHtml(r.value)}</span></div>`)
      .join("");
  }

  async function goOnbNext() {
    syncOnbTextInputs();
    const step = currentOnbStep();
    if (!isOnbStepValid(step)) return;
    const isLast = state.onb.index === state.onb.steps.length - 1;
    if (!isLast) {
      state.onb.index += 1;
      renderOnbStep();
      return;
    }
    showOnbPhase("sending");
    try {
      const result = await api("/register", { method: "POST", body: buildRegisterPayload() });
      state.user = result.user;
      renderOnbSummary();
      showOnbPhase("done");
    } catch (err) {
      showOnbPhase("form");
      renderOnbStep();
      document.getElementById("onb-footer").insertAdjacentHTML(
        "beforeend",
        '<p style="color:var(--danger);font-size:13px;margin-top:10px;text-align:center">Не удалось отправить анкету. Попробуйте ещё раз.</p>'
      );
    }
  }

  // --- Вкладки и переходы -----------------------------------------------------

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  function switchTab(tab) {
    state.tab = tab;
    state.route = "list";
    state.allParticipants = false;
    document.querySelectorAll(".tab-btn").forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === tab));
    document.getElementById("sticky-action").hidden = true;
    renderCurrent();
  }

  function openEvent(id) {
    state.route = "event";
    state.eventId = id;
    state.allParticipants = false;
    renderCurrent();
  }

  function closeEvent() {
    state.route = "list";
    document.getElementById("sticky-action").hidden = true;
    renderCurrent();
  }

  function renderCurrent() {
    if (state.route === "event") { renderEventDetail(); return; }
    if (state.tab === "home") renderHome();
    else if (state.tab === "afisha") renderAfisha();
    else if (state.tab === "about") renderAbout();
    else if (state.tab === "materials") renderMaterials();
    else if (state.tab === "profile") renderProfile();
  }

  // Единая делегированная обработка кликов внутри контента вкладок
  document.getElementById("tab-content").addEventListener("click", (e) => {
    const joinBtn = e.target.closest("[data-join-id]");
    if (joinBtn) { openPayment(joinBtn.dataset.joinId); return; }
    const openBtn = e.target.closest("[data-open-event]");
    if (openBtn) { openEvent(openBtn.dataset.openEvent); return; }
    const goTabBtn = e.target.closest("[data-go-tab]");
    if (goTabBtn) { switchTab(goTabBtn.dataset.goTab); return; }
    const catBtn = e.target.closest("[data-cat]");
    if (catBtn) { state.materialsCategory = catBtn.dataset.cat; renderMaterials(); return; }
    const segBtn = e.target.closest("[data-seg]");
    if (segBtn) { state.seg = segBtn.dataset.seg; renderAfisha(); return; }
    const linkBtn = e.target.closest("[data-material-link]");
    if (linkBtn) { e.preventDefault(); openExternalLink(linkBtn.dataset.materialLink); return; }
    const backBtn = e.target.closest('[data-action="back"]');
    if (backBtn) { closeEvent(); return; }
    const showAllBtn = e.target.closest('[data-action="show-all-participants"]');
    if (showAllBtn) { state.allParticipants = true; renderEventDetail(); return; }
    const retryBtn = e.target.closest('[data-action="retry"]');
    if (retryBtn) { renderCurrent(); return; }
    const faqBtn = e.target.closest("[data-faq-toggle]");
    if (faqBtn) {
      const idx = Number(faqBtn.dataset.faqToggle);
      state.faqOpen = state.faqOpen === idx ? 0 : idx;
      renderAbout();
      return;
    }
    const videoBtn = e.target.closest("[data-play-video]");
    if (videoBtn) { playVideoCard(videoBtn); return; }
  });
  document.getElementById("sticky-action").addEventListener("click", (e) => {
    const joinBtn = e.target.closest("[data-join-id]");
    if (joinBtn) openPayment(joinBtn.dataset.joinId);
  });

  document.getElementById("pay-overlay").addEventListener("click", (e) => {
    if (e.target.closest('[data-action="pay-close"]')) { closePayment(); return; }
    if (e.target.closest('[data-action="pay-agree"]')) { state.pay.agree = !state.pay.agree; renderPaymentSheet(); return; }
    if (e.target.closest('[data-action="pay-submit"]')) { paySubmit(); return; }
    if (e.target.closest('[data-action="pay-retry"]')) { paySubmit(); return; }
  });

  // --- Главная ---------------------------------------------------------------

  async function renderHome() {
    const content = document.getElementById("tab-content");
    content.innerHTML = pageHeaderHtml("Банный орден") + `<div class="scroll-pad">${skeletonHtml(4)}</div>`;
    try {
      const [eventsData, materialsData] = await Promise.all([getEvents(), getMaterials()]);
      const events = eventsData.events.map(withDate);
      const upcoming = events.filter((e) => !e._past).sort(byDateAsc);
      const next = upcoming[0];

      let html = `<div class="scroll-pad">`;
      html += `<div class="card-title" style="font-size:24px;line-height:1.1">Здравствуйте, ${escapeHtml((state.user.fio || "резидент").split(" ")[0])}</div>`;
      if (state.user.company) html += `<div class="profile-company">${escapeHtml(state.user.company)}</div>`;
      if (!state.user.is_active) html += moderationNoticeHtml();

      html += sectionLabelHtml("Ближайшее событие");
      html += next
        ? `<div class="next-card" data-open-event="${next.id}">
            <div class="card-row">
              <div class="date-chip"><div class="day">${dayLabel(next._date)}</div><div class="month">${monthLabelShort(next._date)}</div></div>
              <div style="min-width:0">
                <div class="card-title">${escapeHtml(next.title)}</div>
                <div class="card-meta">${escapeHtml(next.time || "")}${next.time && next.place ? " · " : ""}${escapeHtml(next.place || "")}</div>
                <div class="card-price">${escapeHtml(next.price || "")}</div>
              </div>
            </div>
            <div class="card-actions">${eventActionHtml(next)}</div>
          </div>`
        : `<div class="dashed-box">Заседаний не назначено. Совет объявит ближайшую баню в чате резидентов.</div>`;

      html += sectionLabelHtml("Мои записи", `<span style="font-size:12px;color:var(--muted)">${monthYearLabel(new Date())}</span>`);
      html += calendarHtml(events, new Date());

      html += sectionLabelHtml("Свежее в библиотеке", `<button class="link-btn" data-go-tab="materials">Все материалы</button>`);
      html += materialsData.materials.length
        ? materialsData.materials.slice(0, 2).map(freshMaterialRowHtml).join("")
        : `<div class="dashed-box">Материалов пока нет</div>`;

      html += `</div>`;
      content.innerHTML = pageHeaderHtml("Банный орден") + html;
    } catch (err) {
      content.innerHTML = pageHeaderHtml("Банный орден") + errorStateHtml();
    }
  }

  function calendarHtml(events, monthDate) {
    const year = monthDate.getFullYear();
    const month = monthDate.getMonth();
    const byDay = {};
    events.forEach((e) => {
      if (e._date && e._date.getFullYear() === year && e._date.getMonth() === month) byDay[e._date.getDate()] = e;
    });
    const firstWeekday = (new Date(year, month, 1).getDay() + 6) % 7;
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    let cells = "";
    for (let i = 0; i < firstWeekday; i++) cells += `<div class="calendar-day"></div>`;
    for (let d = 1; d <= daysInMonth; d++) {
      const e = byDay[d];
      const booked = !!(e && e.is_registered);
      const cls = ["calendar-day"];
      if (e) cls.push("has-event");
      if (booked) cls.push("booked");
      const attr = e ? ` data-open-event="${e.id}"` : "";
      const dot = e && e._past ? '<span class="dot"></span>' : "";
      cells += `<div class="${cls.join(" ")}"${attr}>${d}${dot}</div>`;
    }

    const bookedCount = Object.values(byDay).filter((e) => e.is_registered).length;
    const hint = bookedCount === 0
      ? "Оплаченных записей в этом месяце нет."
      : bookedCount === 1
        ? "Одна оплаченная запись в этом месяце."
        : `Оплаченных записей в этом месяце: ${bookedCount}.`;

    return `<div class="calendar-card">
      <div class="calendar-weekdays">${WEEKDAYS_SHORT.slice(1).concat(WEEKDAYS_SHORT[0]).map((w) => `<span>${w}</span>`).join("")}</div>
      <div class="calendar-grid">${cells}</div>
      <div class="calendar-hint">${hint}</div>
    </div>`;
  }

  function freshMaterialRowHtml(m) {
    return `<div class="list-row clickable" data-go-tab="materials">
      <span style="min-width:0"><span class="list-row-title">${escapeHtml(m.title)}</span><span class="list-row-meta">${escapeHtml(m.category || "")}${m.category && m.date ? " · " : ""}${escapeHtml(m.date || "")}</span></span>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style="flex:none;margin-top:3px"><path d="M6 3h7v7M13 3L4 12" stroke="#99A49E" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </div>`;
  }

  // --- Афиша -----------------------------------------------------------------

  function segmentHtml() {
    return `<div class="segment">
      <button data-seg="upcoming" class="${state.seg === "upcoming" ? "active" : ""}">Предстоящие</button>
      <button data-seg="past" class="${state.seg === "past" ? "active" : ""}">Прошедшие</button>
    </div>`;
  }

  function eventCardHtml(e) {
    return `<div class="card clickable" data-open-event="${e.id}">
      <div class="card-row">
        <div class="date-chip"><div class="day">${dayLabel(e._date)}</div><div class="month">${monthLabelShort(e._date)}</div></div>
        <div style="min-width:0;flex:1">
          <div class="card-title">${escapeHtml(e.title)}</div>
          <div class="card-meta">${escapeHtml(e.time || "")}${e.time && e.place ? " · " : ""}${escapeHtml(e.place || "")}</div>
          <div class="card-price">${escapeHtml(e.price || "")}</div>
        </div>
      </div>
      <div class="card-actions">${eventActionHtml(e)}</div>
    </div>`;
  }

  async function renderAfisha() {
    const content = document.getElementById("tab-content");
    content.innerHTML = pageHeaderHtml("Афиша") + `<div class="scroll-pad">${segmentHtml()}${skeletonHtml(3)}</div>`;
    try {
      const data = await getEvents();
      const events = data.events.map(withDate);
      const list = state.seg === "upcoming"
        ? events.filter((e) => !e._past).sort(byDateAsc)
        : events.filter((e) => e._past).sort(byDateDesc);

      let html = `<div class="scroll-pad">${segmentHtml()}`;
      if (list.length) {
        html += `<div style="margin-top:16px">${list.map(eventCardHtml).join("")}</div>`;
      } else {
        const title = state.seg === "upcoming" ? "Афиша пуста" : "Вы ещё не были";
        const text = state.seg === "upcoming" ? "Предстоящих бань пока не назначено." : "Здесь появятся заседания, которые вы посетили.";
        html += `<div class="state-empty"><div class="state-title">${title}</div><p class="state-text">${text}</p></div>`;
      }
      html += `</div>`;
      content.innerHTML = pageHeaderHtml("Афиша") + html;
    } catch (err) {
      content.innerHTML = pageHeaderHtml("Афиша") + errorStateHtml();
    }
  }

  // --- Карточка мероприятия -----------------------------------------------

  async function renderEventDetail() {
    const content = document.getElementById("tab-content");
    const sticky = document.getElementById("sticky-action");
    sticky.hidden = true;
    content.innerHTML = detailTopbarHtml() + `<div class="scroll-pad">${skeletonHtml(3)}</div>`;
    try {
      const data = await api(`/events/${state.eventId}`);
      const e = withDate(data.event);
      const shown = state.allParticipants ? data.attendees : data.attendees.slice(0, 5);

      let html = e.photo
        ? `<div class="detail-cover"><img src="${escapeHtml(e.photo)}" alt="" loading="lazy" onerror="this.closest('.detail-cover').innerHTML='обложка недоступна'"></div>`
        : `<div class="detail-date-banner"><span>${escapeHtml(dateShortLabel(e._date))}</span></div>`;
      html += `<div class="scroll-pad" style="padding-top:20px">`;
      html += `<div class="detail-title">${escapeHtml(e.title)}</div>`;
      html += `<div class="detail-facts">
        <div class="detail-fact"><span>Когда</span><span>${escapeHtml(whenLabel(e._date, e.time))}</span></div>
        <div class="detail-fact"><span>Где</span><span>${escapeHtml(e.place || "—")}</span></div>
        <div class="detail-fact"><span>Взнос</span><span>${escapeHtml(e.price || "—")}</span></div>
      </div>`;
      if (e.description) html += `<p class="detail-desc">${escapeHtml(e.description)}</p>`;

      html += `<div class="participants-title"><span>Участники</span><span>${data.attendees_count} резидент${pluralSuffix(data.attendees_count)}</span></div>`;
      html += shown.length
        ? shown.map((p) => `<div class="participant-row"><span class="avatar small">${escapeHtml(initials(p.fio))}</span><span class="participant-info"><span class="participant-name">${escapeHtml(p.fio)}</span><span class="participant-niche">${escapeHtml(p.niche || "")}</span></span></div>`).join("")
        : `<div class="dashed-box">Пока никто не записался — станьте первым!</div>`;
      if (!state.allParticipants && data.attendees.length > 5) {
        html += `<button class="btn-secondary" data-action="show-all-participants" style="margin-top:10px">Показать всех</button>`;
      }
      html += `</div>`;

      content.innerHTML = detailTopbarHtml() + html;

      const actionHtml = eventActionHtml(e, { sticky: true });
      sticky.innerHTML = actionHtml;
      sticky.hidden = actionHtml === "";
    } catch (err) {
      content.innerHTML = detailTopbarHtml() + errorStateHtml();
    }
  }

  function pluralSuffix(n) {
    const mod10 = n % 10;
    const mod100 = n % 100;
    if (mod100 >= 11 && mod100 <= 14) return "ов";
    if (mod10 === 1) return "";
    if (mod10 >= 2 && mod10 <= 4) return "а";
    return "ов";
  }

  function detailTopbarHtml() {
    return `<div class="detail-topbar"><button class="back-btn" data-action="back" aria-label="Назад"><svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M12 4l-6 6 6 6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button><span>Событие</span></div>`;
  }

  // --- Материалы -------------------------------------------------------------

  function materialCardHtml(m) {
    const linkAttr = m.link ? ` data-material-link="${escapeHtml(m.link)}"` : "";
    return `<div class="card${m.link ? " clickable" : ""}"${linkAttr}>
      <div style="display:flex;gap:12px;align-items:flex-start">
        <div style="min-width:0;flex:1">
          <div style="font-size:16px;font-weight:500;line-height:1.32">${escapeHtml(m.title)}</div>
          ${m.description ? `<div class="material-desc">${escapeHtml(m.description)}</div>` : ""}
        </div>
        ${m.link ? '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" style="flex:none;margin-top:4px"><path d="M6 3h7v7M13 3L4 12" stroke="#99A49E" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' : ""}
      </div>
      <div class="material-meta">
        ${m.category ? `<span class="tag">${escapeHtml(m.category)}</span>` : ""}
        ${m.date ? `<span style="font-size:12px;color:var(--muted)">${escapeHtml(m.date)}</span>` : ""}
      </div>
    </div>`;
  }

  async function renderMaterials() {
    const content = document.getElementById("tab-content");
    content.innerHTML = pageHeaderHtml("Материалы") + `<div class="scroll-pad">${skeletonHtml(4)}</div>`;
    try {
      const data = await getMaterials();
      const cats = ["Все", ...new Set(data.materials.map((m) => m.category).filter(Boolean))];
      if (!cats.includes(state.materialsCategory)) state.materialsCategory = "Все";
      const filtered = state.materialsCategory === "Все" ? data.materials : data.materials.filter((m) => m.category === state.materialsCategory);

      let html = `<div class="scroll-pad"><div class="chip-row" style="padding-bottom:4px">${cats
        .map((c) => `<button class="chip-filter${c === state.materialsCategory ? " active" : ""}" data-cat="${escapeHtml(c)}">${escapeHtml(c)}</button>`)
        .join("")}</div>`;

      if (data.materials.length === 0) {
        html += `<div class="state-empty"><div class="state-title">Библиотека пуста</div><p class="state-text">Материалы появляются после разборов и выступлений.</p></div>`;
      } else if (filtered.length) {
        html += `<div style="margin-top:12px">${filtered.map(materialCardHtml).join("")}</div>`;
      } else {
        html += `<div class="state-empty"><div class="state-title">Ничего не нашлось</div><p class="state-text">В категории «${escapeHtml(state.materialsCategory)}» пока нет материалов.</p><button class="btn-secondary" data-cat="Все" style="margin-top:20px;width:auto;padding:0 22px;display:inline-flex;align-items:center;justify-content:center">Сбросить фильтр</button></div>`;
      }
      html += `</div>`;
      content.innerHTML = pageHeaderHtml("Материалы") + html;
    } catch (err) {
      content.innerHTML = pageHeaderHtml("Материалы") + errorStateHtml();
    }
  }

  // --- Профиль ---------------------------------------------------------------

  function splitChips(str) {
    return (str || "").split(",").map((s) => s.trim()).filter(Boolean);
  }

  function profileFieldRowHtml(f) {
    if (f.chips) {
      const chipsHtml = f.chips.length
        ? f.chips.map((c) => `<span class="chip">${escapeHtml(c)}</span>`).join("")
        : '<span class="field-value" style="color:var(--muted)">—</span>';
      return `<div class="field-row"><span class="field-label">${escapeHtml(f.label)}</span><span class="field-chips">${chipsHtml}</span></div>`;
    }
    const muted = !f.value || f.value === "не указан" || f.value === "не указана";
    return `<div class="field-row"><span class="field-label">${escapeHtml(f.label)}</span><span class="field-value"${muted ? ' style="color:var(--muted)"' : ""}>${escapeHtml(f.value || "—")}</span></div>`;
  }

  async function renderProfile() {
    const content = document.getElementById("tab-content");
    content.innerHTML = pageHeaderHtml("Профиль") + `<div class="scroll-pad">${skeletonHtml(3)}</div>`;
    try {
      const data = await getProfile();
      const u = data.user;
      state.user = { ...state.user, ...u };

      let html = `<div class="scroll-pad">`;
      html += `<div class="profile-head">
        <span class="avatar">${escapeHtml(initials(u.fio))}</span>
        <div style="min-width:0">
          <div class="profile-name">${escapeHtml(u.fio)}</div>
          ${u.company ? `<div class="profile-company">${escapeHtml(u.company)}</div>` : ""}
          ${u.is_active
            ? '<span class="badge badge-active" style="display:inline-flex;margin-top:9px">Активный резидент</span>'
            : '<span class="badge badge-moderation" style="display:inline-flex;margin-top:9px">На модерации</span>'}
        </div>
      </div>`;

      const fields = [
        { label: "ФИО", value: u.fio },
        { label: "Компания", value: u.company },
        { label: "Должность", value: u.position || "не указана" },
        { label: "Сфера", chips: splitChips(u.sphere) },
        { label: "Запрос", chips: splitChips(u.request) },
        { label: "Город", value: u.city },
        { label: "Телефон", value: u.phone || "не указан" },
        { label: "Telegram", value: u.telegram_username ? "@" + u.telegram_username : "не указан" },
        { label: "В Ордене с", value: u.since || "—" },
        { label: "Сайт", value: "не указан" },
      ];
      html += sectionLabelHtml("Анкета") + `<div>${fields.map(profileFieldRowHtml).join("")}</div>`;

      html += sectionLabelHtml("Посещу");
      html += data.upcoming_events.length
        ? data.upcoming_events
            .map((e) => `<div class="list-row clickable" data-open-event="${e.id}"><span style="min-width:0"><span class="list-row-title">${escapeHtml(e.title)}</span><span class="list-row-meta">${escapeHtml(shortDate(e.date))}${e.time ? " · " + escapeHtml(e.time) : ""}</span></span><span class="list-row-status">Записан</span></div>`)
            .join("")
        : `<div class="dashed-box">Записей нет</div>`;

      html += sectionLabelHtml("Посетил");
      html += data.past_events.length
        ? data.past_events
            .map((e) => `<div class="list-row visited"><span style="min-width:0"><span class="list-row-title">${escapeHtml(e.title)}</span><span class="list-row-meta">${escapeHtml(shortDate(e.date))}</span></span><span class="list-row-status muted">Вы посетили</span></div>`)
            .join("")
        : `<div class="dashed-box">Пока ничего не посетили</div>`;

      html += sectionLabelHtml("Достижения");
      if (data.achievements.length) {
        html += data.achievements
          .map((a) => `<div class="card"><div class="card-title" style="font-size:20px">🏆 ${escapeHtml(a.title)}</div>${a.description ? `<p class="material-desc">${escapeHtml(a.description)}</p>` : ""}<div class="card-meta">${escapeHtml(a.date)}</div></div>`)
          .join("");
      } else {
        html += `<div class="achievements-box"><div class="state-title">Пока не отмечены</div><p class="state-text">Знаки Ордена присуждает совет — за выступления, приглашённых резидентов и закрытые сделки.</p></div>`;
      }

      html += `</div>`;
      content.innerHTML = pageHeaderHtml("Профиль") + html;
    } catch (err) {
      content.innerHTML = pageHeaderHtml("Профиль") + errorStateHtml();
    }
  }

  // --- О нас -------------------------------------------------------------

  function videoCardHtml(v) {
    return `<button type="button" class="video-card" data-play-video>
      <video src="${escapeHtml(v.src)}" preload="metadata" playsinline muted></video>
      <span class="video-play"><svg width="18" height="20" viewBox="0 0 20 22" fill="none"><path d="M4 3l13 8-13 8V3z" fill="#213902"/></svg></span>
      <span class="video-duration" data-video-duration></span>
      <span class="video-caption"><span class="t">${escapeHtml(v.title)}</span><span class="s">${escapeHtml(v.sub)}</span></span>
    </button>`;
  }

  function attachVideoDurationHandlers() {
    document.querySelectorAll(".video-card video").forEach((video) => {
      video.addEventListener("loadedmetadata", () => {
        const card = video.closest(".video-card");
        const badge = card && card.querySelector("[data-video-duration]");
        if (badge && isFinite(video.duration)) {
          const total = Math.round(video.duration);
          const m = Math.floor(total / 60);
          const s = String(total % 60).padStart(2, "0");
          badge.textContent = `${m}:${s}`;
        }
      }, { once: true });
    });
  }

  function playVideoCard(btn) {
    const card = btn.closest(".video-card");
    const video = card && card.querySelector("video");
    if (!video) return;
    card.classList.add("playing");
    video.controls = true;
    video.muted = false;
    video.play().catch(() => {});
  }

  function renderAbout() {
    const content = document.getElementById("tab-content");
    let html = `<div class="scroll-pad">`;
    html += `<div class="about-card">
      <p><span class="accent">Банный Орден</span> — это закрытое сообщество предпринимателей, где мы объединяем сильных людей для нетворкинга, поддержки и совместного роста.</p>
      <p>Наши встречи проходят в формате бань, выездов и неформальных мероприятий, где рождаются партнёрства и крепкая дружба.</p>
    </div>`;
    html += `<div class="about-highlight">
      <div class="about-eyebrow">Главная идея</div>
      <p>Собирать сильных предпринимателей в круг, где они могут помогать друг другу, развивать свои проекты и при этом оставаться собой.</p>
    </div>`;
    html += `<div class="about-divider"><span class="line"></span><span class="label">Наши люди — наша сила</span><span class="line"></span></div>`;
    html += `<div class="video-grid">${ABOUT_VIDEOS.map(videoCardHtml).join("")}</div>`;
    html += sectionLabelHtml("Вопросы об Ордене");
    html += ABOUT_FAQ.map((f, i) => {
      const idx = i + 1;
      const open = state.faqOpen === idx;
      return `<div class="faq-item">
        <button type="button" class="faq-q" data-faq-toggle="${idx}"><span>${escapeHtml(f.q)}</span><span class="faq-sign">${open ? "−" : "+"}</span></button>
        ${open ? `<div class="faq-a">${f.paras.map((p) => `<p>${escapeHtml(p)}</p>`).join("")}</div>` : ""}
      </div>`;
    }).join("");
    html += `</div>`;
    content.innerHTML = pageHeaderHtml("О нас") + html;
    attachVideoDurationHandlers();
  }

  // --- Оплата участия (визуальная имитация Продамуса) -----------------------

  function findCachedEvent(id) {
    const idStr = String(id);
    const list = state.cache.events && state.cache.events.events;
    return (list && list.find((e) => String(e.id) === idStr)) || null;
  }

  async function openPayment(id) {
    state.pay = { eventId: id, phase: "form", agree: false, event: findCachedEvent(id) };
    document.getElementById("pay-overlay").hidden = false;
    renderPaymentSheet();
    if (!state.pay.event) {
      try {
        const data = await api(`/events/${id}`);
        if (state.pay.eventId === id) {
          state.pay.event = data.event;
          renderPaymentSheet();
        }
      } catch (err) {
        // оставим форму с прочерками — id события уже есть, оплата всё равно сработает
      }
    }
  }

  function closePayment() {
    document.getElementById("pay-overlay").hidden = true;
    state.pay = { eventId: null, phase: "form", agree: false };
  }

  function renderPaymentSheet() {
    const body = document.getElementById("pay-body");
    const p = state.pay;
    const e = p.event ? withDate(p.event) : null;
    const price = e ? e.price || "" : "";

    if (p.phase === "form") {
      const rows = e
        ? [
            { label: "Событие", value: e.title },
            { label: "Когда", value: whenLabel(e._date, e.time) },
            { label: "Место", value: e.place },
          ]
        : [];
      body.innerHTML = `
        <div class="pay-title">Оплата участия</div>
        <div class="pay-rows">${rows.map((r) => `<div class="pay-row"><span>${escapeHtml(r.label)}</span><span>${escapeHtml(r.value || "—")}</span></div>`).join("")}</div>
        <div class="pay-total"><span>К оплате</span><span class="amount">${escapeHtml(price || "—")}</span></div>
        <button type="button" class="pay-agree" data-action="pay-agree">
          <span class="pay-check${p.agree ? " checked" : ""}">${p.agree ? '<svg width="13" height="13" viewBox="0 0 16 16" fill="none"><path d="M3.5 8.5l3 3 6-7" stroke="#213902" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>' : ""}</span>
          <span>Согласен с условиями участия и офертой Банного Ордена</span>
        </button>
        <button type="button" class="btn-primary" data-action="pay-submit" style="margin-top:12px" ${p.agree ? "" : "disabled"}>Перейти к оплате${price ? " · " + escapeHtml(price) : ""}</button>
        <div class="pay-secure">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><rect x="3" y="7" width="10" height="7" rx="2" stroke="#99A49E" stroke-width="1.4"/><path d="M5.5 7V5.5a2.5 2.5 0 015 0V7" stroke="#99A49E" stroke-width="1.4"/></svg>
          Оплата через Продамус · защищённое соединение
        </div>`;
    } else if (p.phase === "redirect") {
      body.innerHTML = `<div class="pay-spinner-wrap">
        <span class="spinner"></span>
        <span style="font-size:15px">Открываем защищённую страницу Продамус</span>
        <span class="hint">Сейчас откроется окно оплаты — после оплаты вернитесь в Telegram и откройте мини-апп заново</span>
      </div>`;
    } else if (p.phase === "fail") {
      body.innerHTML = `<div class="pay-status">
        <div class="pay-status-icon fail"><svg width="24" height="24" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="#E28371" stroke-width="1.6"/><path d="M12 7.5v5.5M12 16.2v.6" stroke="#E28371" stroke-width="1.8" stroke-linecap="round"/></svg></div>
        <div class="pay-status-title">Оплата не прошла</div>
        <p class="pay-status-text">${escapeHtml(p.errorMessage || "Не удалось начать оплату. Попробуйте ещё раз.")}</p>
        <button type="button" class="btn-primary" data-action="pay-retry" style="margin-top:18px">Повторить оплату</button>
        <button type="button" class="btn-secondary" data-action="pay-close" style="margin-top:8px">Закрыть</button>
      </div>`;
    }
  }

  async function paySubmit() {
    const p = state.pay;
    if (p.phase === "form" && !p.agree) return;
    p.phase = "redirect";
    renderPaymentSheet();
    try {
      const data = await api(`/events/${p.eventId}/signup`, { method: "POST" });
      if (state.pay.eventId !== p.eventId) return;
      if (tg && tg.openLink) tg.openLink(data.payment_url);
      else window.location.href = data.payment_url;
    } catch (err) {
      if (state.pay.eventId !== p.eventId) return;
      state.pay.phase = "fail";
      state.pay.errorMessage = err.message === "price_not_set"
        ? "Для этого события ещё не указана цена участия — обратитесь к администратору."
        : err.message === "already_registered"
          ? "Вы уже записаны на это событие."
          : "Не удалось начать оплату. Попробуйте ещё раз.";
      renderPaymentSheet();
    }
  }

  init();
})();
