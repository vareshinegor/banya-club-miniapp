/* Админ-панель Банного Ордена — клиент. Весь интерфейс строится через DOM API
   (h()/textContent): анкеты заполняют посторонние люди, innerHTML с их текстом
   был бы дырой. Inline-скриптов нет (CSP script-src 'self'). */
(() => {
  "use strict";

  const state = {
    csrf: "",
    login: "",
    users: [],
    pendingCount: null,
    usersTier: "all",
    usersQuery: "",
    usersSort: { key: "registered", dir: -1 },
    eventsSeg: "upcoming",
  };

  const view = document.getElementById("view");
  let renderSeq = 0;

  // ---------------------------------------------------------------- DOM utils

  function append(el, children) {
    for (const c of children.flat(Infinity)) {
      if (c == null || c === false) continue;
      el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
  }

  function h(tag, props, ...children) {
    const el = document.createElement(tag);
    let value;
    if (props) {
      for (const [k, v] of Object.entries(props)) {
        if (v == null || v === false) continue;
        if (k === "class") el.className = v;
        else if (k === "text") el.textContent = v;
        else if (k === "value") value = v;
        else if (k === "checked") el.checked = !!v;
        else if (k === "disabled") el.disabled = !!v;
        else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
        else el.setAttribute(k, v === true ? "" : v);
      }
    }
    append(el, children);
    if (value !== undefined) el.value = value; // после options у select
    return el;
  }

  const ICONS = {
    dashboard: ["M3 3h7v9H3z", "M14 3h7v5h-7z", "M14 12h7v9h-7z", "M3 16h7v5H3z"],
    users: ["M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2", "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z", "M22 21v-2a4 4 0 0 0-3-3.9", "M16 3.1a4 4 0 0 1 0 7.8"],
    calendar: ["M3 6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", "M16 2v4", "M8 2v4", "M3 10h18"],
    tag: ["M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L2 12V2h10l8.6 8.6a2 2 0 0 1 0 2.8z", "M7 7h.01"],
    book: ["M4 19.5A2.5 2.5 0 0 1 6.5 17H20", "M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"],
    coin: ["M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z", "M12 6v12", "M9 9.5h4.5a1.8 1.8 0 0 1 0 3.5H9.5a1.8 1.8 0 0 0 0 3.5H15"],
    log: ["M8 6h13", "M8 12h13", "M8 18h13", "M3 6h.01", "M3 12h.01", "M3 18h.01"],
  };

  function icon(name) {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("width", "18");
    svg.setAttribute("height", "18");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.7");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    for (const d of ICONS[name] || []) {
      const p = document.createElementNS(ns, "path");
      p.setAttribute("d", d);
      svg.append(p);
    }
    return svg;
  }

  // ------------------------------------------------------------------- format

  const MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
  const WEEKDAYS = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];
  const TIER = { resident: "Резидент", non_resident: "Нерезидент", pending: "На рассмотрении" };
  const TIER_ORDER = { pending: 0, non_resident: 1, resident: 2 };
  const STATUSES = ["на рассмотрении", "нерезидент", "резидент"];

  function dateLabel(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    if (!m) return iso || "—";
    const d = new Date(+m[1], +m[2] - 1, +m[3]);
    return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${WEEKDAYS[d.getDay()]}`;
  }
  const money = (n) => `${Math.round(n || 0).toLocaleString("ru-RU")} ₽`;
  const num = (n) => Math.round(n || 0).toLocaleString("ru-RU");
  const initials = (fio) => (fio || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("") || "?";

  function tierBadge(tier, label) {
    return h("span", { class: `badge badge-${tier}`, text: label || TIER[tier] || tier });
  }

  function signupBadge(status) {
    const cls = status === "оплачено" ? "paid" : status === "отклонено" ? "failed" : "wait";
    return h("span", { class: `badge badge-${cls}`, text: status || "—" });
  }

  function avatar(user, large) {
    const box = h("span", { class: `avatar${large ? " lg" : ""}` });
    if (user.avatar) box.append(h("img", { src: user.avatar, alt: "", loading: "lazy" }));
    else box.textContent = initials(user.fio);
    return box;
  }

  function personCell(u) {
    return h(
      "div", { class: "person" },
      avatar(u),
      h("div", {}, h("div", { class: "name", text: u.fio || "(без имени)" }), u.username ? h("span", { class: "sub", text: "@" + u.username }) : null),
    );
  }

  // --------------------------------------------------------------------- toast

  function toast(message, kind) {
    const el = h("div", { class: `toast ${kind || ""}`, text: message });
    document.getElementById("toasts").append(el);
    setTimeout(() => el.remove(), kind === "error" ? 6500 : 3500);
  }

  // --------------------------------------------------------------------- api

  async function api(path, opts = {}) {
    const method = opts.method || "GET";
    const init = { method, headers: {}, credentials: "same-origin" };
    if (method !== "GET") init.headers["X-CSRF-Token"] = state.csrf;
    if (opts.json !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(opts.json);
    }
    if (opts.form) init.body = opts.form;
    const res = await fetch("/admin/api" + path, init);
    if (res.status === 401) {
      location.href = "/admin/login";
      throw new Error("Нужно войти");
    }
    let data = null;
    try { data = await res.json(); } catch (e) { /* не JSON */ }
    if (!res.ok) {
      const err = new Error((data && data.message) || `Ошибка ${res.status}`);
      err.code = data && data.error;
      throw err;
    }
    return data;
  }

  // Выполнить действие: заблокировать кнопку, показать ошибку тостом.
  async function run(button, action, okMessage) {
    if (button) button.disabled = true;
    try {
      const result = await action();
      if (okMessage) toast(okMessage, "ok");
      return result === undefined ? true : result;
    } catch (err) {
      toast(err.message, "error");
      return false;
    } finally {
      if (button) button.disabled = false;
    }
  }

  // -------------------------------------------------------------------- modal

  function openModal(title, body, opts = {}) {
    const root = document.getElementById("modal-root");
    const back = h("div", { class: "modal-back" });
    const box = h("div", { class: `modal${opts.wide ? " wide" : ""}`, role: "dialog", "aria-modal": "true" }, h("h3", { text: title }), body);
    back.append(box);
    const close = () => {
      back.remove();
      document.removeEventListener("keydown", onKey);
    };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    back.addEventListener("mousedown", (e) => { if (e.target === back) close(); });
    document.addEventListener("keydown", onKey);
    root.append(back);
    const first = box.querySelector("input, textarea, select");
    if (first) first.focus();
    return { close, box };
  }

  function confirmBox(message, opts = {}) {
    return new Promise((resolve) => {
      let modal;
      const done = (v) => { modal.close(); resolve(v); };
      const body = h(
        "div", {},
        h("p", { text: message }),
        h("div", { class: "modal-actions" },
          h("button", { class: "btn btn-ghost", type: "button", text: "Отмена", onclick: () => done(false) }),
          h("button", { class: `btn ${opts.danger ? "btn-danger" : "btn-primary"}`, type: "button", text: opts.confirmText || "Подтвердить", onclick: () => done(true) }),
        ),
      );
      modal = openModal(opts.title || "Подтвердите действие", body);
    });
  }

  // -------------------------------------------------------------------- table

  function table(columns, rows, opts = {}) {
    const head = h("tr", {}, columns.map((c) => {
      const th = h("th", { class: `${c.cls || ""}${c.sort ? " sortable" : ""}`, text: c.label });
      if (c.sort && opts.onSort) {
        const s = opts.sort || {};
        if (s.key === c.sort) th.textContent = c.label + (s.dir > 0 ? " ↑" : " ↓");
        th.addEventListener("click", () => opts.onSort(c.sort));
      }
      return th;
    }));
    const body = h("tbody", {});
    if (!rows.length) {
      body.append(h("tr", {}, h("td", { class: "empty", colspan: columns.length, text: opts.empty || "Ничего нет" })));
    }
    for (const row of rows) {
      const tr = h("tr", { class: opts.onRow ? "clickable" : "" });
      for (const c of columns) tr.append(h("td", { class: c.cls || "" }, c.render(row)));
      if (opts.onRow) tr.addEventListener("click", (e) => { if (!e.target.closest("a, button, input, select")) opts.onRow(row); });
      body.append(tr);
    }
    return h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, head), body));
  }

  function pageHead(title, sub, actions) {
    return h(
      "div", { class: "page-head" },
      h("div", {}, h("h1", { text: title }), sub ? h("div", { class: "sub", text: sub }) : null),
      actions ? h("div", { class: "page-actions" }, actions) : null,
    );
  }

  function setView(...nodes) {
    view.replaceChildren(...nodes.flat().filter(Boolean));
    window.scrollTo(0, 0);
  }

  function field(label, input, hint) {
    return h("label", { class: "field" }, h("span", { text: label }), input, hint ? h("small", { text: hint }) : null);
  }

  function setPending(n) {
    state.pendingCount = n;
    const el = document.getElementById("pending-count");
    if (el) {
      el.textContent = n || "";
      el.hidden = !n;
    }
  }

  // ---------------------------------------------------------------- dashboard

  async function pageDashboard(ctx) {
    const d = await api("/dashboard");
    setPending(d.counts.pending);

    const stat = (label, value, opts = {}) =>
      h("div", { class: `stat${opts.href ? " link" : ""}${opts.warn ? " warn" : ""}`, onclick: opts.href ? () => { location.hash = opts.href; } : null },
        h("div", { class: "label", text: label }), h("div", { class: "value", text: value }));

    const upcoming = table(
      [
        { label: "Дата", cls: "nowrap", render: (e) => [dateLabel(e.date), e.time ? h("span", { class: "sub", text: e.time }) : null] },
        { label: "Событие", render: (e) => [e.title, e.free ? h("span", { class: "badge badge-free", text: "бесплатно" }) : null] },
        { label: "Записано", cls: "num", render: (e) => `${e.people} чел. / ${e.tickets} бил.` },
        { label: "Ждут оплаты", cls: "num", render: (e) => e.pending || "—" },
        { label: "Деньгами", cls: "num", render: (e) => (e.cash ? money(e.cash) : "—") },
        { label: "Дубиками", cls: "num", render: (e) => (e.points ? num(e.points) : "—") },
      ],
      d.upcoming,
      { empty: "Предстоящих событий нет", onRow: (e) => { location.hash = `#/events/${e.id}/signups`; } },
    );

    const pending = d.pending.length
      ? d.pending.map((u) => h(
          "div", { class: "list-row" },
          h("div", { class: "main" }, personCell(u), h("span", { class: "sub", text: [u.company, u.city].filter(Boolean).join(" · ") })),
          h("div", { class: "page-actions" },
            h("button", { class: "btn btn-sm", type: "button", text: "Открыть", onclick: () => { location.hash = `#/users/${u.telegram_id}`; } }),
            h("button", {
              class: "btn btn-sm btn-primary", type: "button", text: "Одобрить",
              onclick: async (e) => {
                const ok = await run(e.currentTarget, () => api(`/users/${u.telegram_id}/status`, { method: "POST", json: { status: "нерезидент" } }), `${u.fio}: одобрен (нерезидент)`);
                if (ok) route();
              },
            }),
          ),
        ))
      : h("div", { class: "muted", text: "Новых заявок нет" });

    const recent = d.recent_signups.length
      ? d.recent_signups.map((s) => h(
          "div", { class: "list-row" },
          h("div", { class: "main" }, h("a", { href: `#/users/${s.telegram_id}`, text: s.fio }), h("div", { class: "sub", text: `${s.event}${s.quantity > 1 ? ` · ${s.quantity} бил.` : ""}` })),
          h("span", { class: "muted nowrap", text: s.date }),
        ))
      : h("div", { class: "muted", text: "Записей пока нет" });

    ctx.view(
      pageHead("Обзор", "Что происходит в клубе"),
      h("div", { class: "grid grid-4", style: "margin-bottom:18px" },
        stat("Резиденты", num(d.counts.resident), { href: "#/users?tier=resident" }),
        stat("Нерезиденты", num(d.counts.non_resident), { href: "#/users?tier=non_resident" }),
        stat("Заявки на рассмотрении", num(d.counts.pending), { href: "#/users?tier=pending", warn: d.counts.pending > 0 }),
        stat("Дубиков в обороте", num(d.points_in_circulation), { href: "#/points" }),
      ),
      h("div", { class: "grid grid-main" },
        h("div", {}, h("div", { class: "card" }, h("h2", {}, "Ближайшие события"), upcoming)),
        h("div", {},
          h("div", { class: "card" }, h("h2", {}, "Новые заявки", h("span", { class: "count", text: d.counts.pending || "" })), pending),
          h("div", { class: "card" }, h("h2", {}, "Последние записи"), recent),
        ),
      ),
    );
  }

  // -------------------------------------------------------------------- users

  function sortUsers(list) {
    const { key, dir } = state.usersSort;
    const val = (u) => {
      if (key === "fio") return (u.fio || "").toLowerCase();
      if (key === "status") return TIER_ORDER[u.tier];
      if (key === "balance") return u.balance;
      if (key === "signups") return u.signups;
      return u.registered || "";
    };
    return [...list].sort((a, b) => (val(a) > val(b) ? 1 : val(a) < val(b) ? -1 : 0) * dir);
  }

  function filterUsers() {
    const q = state.usersQuery.trim().toLowerCase();
    return state.users.filter((u) => {
      if (state.usersTier !== "all" && u.tier !== state.usersTier) return false;
      if (!q) return true;
      return [u.fio, u.company, u.position, u.phone, u.username, u.telegram_id, u.city, u.sphere].some((v) => (v || "").toLowerCase().includes(q));
    });
  }

  async function pageUsers(ctx, query) {
    const params = new URLSearchParams(query || "");
    if (params.get("tier")) state.usersTier = params.get("tier");
    const data = await api("/users");
    state.users = data.users;
    setPending(state.users.filter((u) => u.tier === "pending").length);

    const counts = { all: state.users.length, resident: 0, non_resident: 0, pending: 0 };
    for (const u of state.users) counts[u.tier] += 1;

    const holder = h("div", {});
    const renderTable = () => {
      holder.replaceChildren(table(
        [
          { label: "Человек", sort: "fio", render: personCell },
          { label: "Компания", render: (u) => [u.company || "—", u.position ? h("span", { class: "sub", text: u.position }) : null] },
          { label: "Город", render: (u) => u.city || "—" },
          { label: "Телефон", cls: "nowrap", render: (u) => u.phone || "—" },
          { label: "Статус", sort: "status", render: (u) => tierBadge(u.tier, u.status || "—") },
          { label: "Дубики", sort: "balance", cls: "num", render: (u) => (u.balance ? num(u.balance) : "—") },
          { label: "Записей", sort: "signups", cls: "num", render: (u) => u.signups || "—" },
          { label: "Заявка", sort: "registered", cls: "nowrap", render: (u) => (u.registered || "—").slice(0, 10) },
          { label: "Согласие", render: (u) => (u.consent ? h("span", { class: "plus", title: u.consent, text: "✓" }) : h("span", { class: "muted", text: "—" })) },
        ],
        sortUsers(filterUsers()),
        {
          sort: state.usersSort,
          onSort: (key) => {
            state.usersSort = state.usersSort.key === key ? { key, dir: -state.usersSort.dir } : { key, dir: key === "fio" ? 1 : -1 };
            renderTable();
          },
          onRow: (u) => { location.hash = `#/users/${u.telegram_id}`; },
          empty: "Никого не нашлось",
        },
      ));
    };

    const segment = h("div", { class: "segment" });
    const tabs = [["all", "Все"], ["resident", "Резиденты"], ["non_resident", "Нерезиденты"], ["pending", "На рассмотрении"]];
    const renderSegment = () => segment.replaceChildren(...tabs.map(([key, label]) => h(
      "button", {
        type: "button", class: state.usersTier === key ? "active" : "",
        onclick: () => { state.usersTier = key; renderSegment(); renderTable(); },
      },
      label, h("span", { class: "n", text: counts[key] }),
    )));
    renderSegment();

    const search = h("input", {
      class: "input", type: "search", placeholder: "Поиск: имя, компания, телефон, @username…", value: state.usersQuery,
      oninput: (e) => { state.usersQuery = e.target.value; renderTable(); },
    });
    renderTable();

    ctx.view(
      pageHead("Люди", "Резиденты, нерезиденты и заявки на рассмотрении",
        h("a", { class: "btn", href: "/admin/api/export/users.csv", text: "Экспорт CSV" })),
      h("div", { class: "toolbar" }, segment, search),
      holder,
    );
  }

  // ---------------------------------------------------------------- user card

  async function pageUser(ctx, telegramId) {
    const d = await api(`/users/${encodeURIComponent(telegramId)}`);
    const u = d.user;
    const tid = u.telegram_id;

    // --- статус
    const statusSelect = h("select", { class: "input input-select", value: STATUSES.find((x) => x === (u.status || "").toLowerCase()) || "на рассмотрении" },
      STATUSES.map((s) => h("option", { value: s, text: s })));
    const statusBtn = h("button", {
      class: "btn btn-primary", type: "button", text: "Сохранить статус",
      onclick: async (e) => {
        const btn = e.currentTarget;
        const next = statusSelect.value;
        if (next === u.status) return toast("Статус не изменился");
        const down = TIER_ORDER[next === "резидент" ? "resident" : next === "нерезидент" ? "non_resident" : "pending"] < TIER_ORDER[u.tier];
        if (down && !(await confirmBox(`Понизить статус «${u.fio}» до «${next}»? Человек потеряет доступ, который давал прежний статус.`, { confirmText: "Понизить", danger: true }))) return;
        const ok = await run(btn, () => api(`/users/${tid}/status`, { method: "POST", json: { status: next } }), `Статус: ${next}`);
        if (ok) route();
      },
    });

    // --- анкета
    const longFields = new Set(["Запрос", "Предложение", "Сфера"]);
    const inputs = {};
    const formFields = d.fields.map(({ name, value }) => {
      const el = longFields.has(name)
        ? h("textarea", { class: "", value })
        : h("input", { type: "text", value });
      inputs[name] = el;
      return field(name, el);
    });
    const saveBtn = h("button", {
      class: "btn btn-primary", type: "button", text: "Сохранить анкету",
      onclick: async (e) => {
        const payload = {};
        for (const [name, el] of Object.entries(inputs)) payload[name] = el.value;
        const ok = await run(e.currentTarget, () => api(`/users/${tid}`, { method: "PATCH", json: payload }), "Анкета сохранена");
        if (ok) route();
      },
    });

    // --- аватар
    const fileInput = h("input", {
      type: "file", accept: "image/*", hidden: true,
      onchange: async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const form = new FormData();
        form.append("photo", file);
        const ok = await run(null, () => api(`/users/${tid}/avatar`, { method: "POST", form }), "Фото обновлено");
        if (ok) route();
      },
    });

    // --- дубики
    const amount = h("input", { class: "input", type: "number", step: "1", placeholder: "+3000 или −1000" });
    const reason = h("input", { class: "input", type: "text", placeholder: "Причина (видна в истории)", maxlength: "120" });
    const pointsBtn = h("button", {
      class: "btn btn-primary", type: "button", text: "Применить",
      onclick: async (e) => {
        const ok = await run(e.currentTarget, () => api(`/users/${tid}/points`, { method: "POST", json: { amount: amount.value, reason: reason.value } }), "Баланс обновлён");
        if (ok) route();
      },
    });
    const ledger = d.ledger.length
      ? d.ledger.slice(0, 12).map((l) => h(
          "div", { class: "list-row" },
          h("div", { class: "main" }, l.reason || "—", h("div", { class: "sub", text: l.date })),
          h("strong", { class: l.amount > 0 ? "plus" : "minus", text: `${l.amount > 0 ? "+" : "−"}${num(Math.abs(l.amount))}` }),
        ))
      : h("div", { class: "muted", text: "Операций не было" });

    // --- записи
    const signups = table(
      [
        { label: "Событие", render: (s) => [h("a", { href: `#/events/${s.event_id}/signups`, text: s.event }), h("span", { class: "sub", text: dateLabel(s.event_date) })] },
        { label: "Статус", render: (s) => signupBadge(s.status) },
        { label: "Билетов", cls: "num", render: (s) => s.quantity },
        { label: "Деньгами", cls: "num", render: (s) => (s.cash ? money(s.cash) : "—") },
        { label: "Дубиками", cls: "num", render: (s) => (s.points ? num(s.points) : "—") },
        { label: "Промокод", render: (s) => s.promo || "—" },
      ],
      d.signups,
      { empty: "Записей нет" },
    );

    // --- рефералы
    const refs = [];
    refs.push(d.invited_by
      ? h("div", { class: "list-row" },
          h("div", { class: "main" }, "Пригласил: ", h("a", { href: `#/users/${d.invited_by.telegram_id}`, text: d.invited_by.fio }),
            h("div", { class: "sub", text: d.invited_by.rewarded ? `награда выдана ${d.invited_by.rewarded}` : "награда ещё не выдана" })))
      : h("div", { class: "muted", text: "Пришёл сам (по рефералке не регистрировался)" }));
    for (const r of d.invited) {
      refs.push(h("div", { class: "list-row" },
        h("div", { class: "main" }, h("a", { href: `#/users/${r.telegram_id}`, text: r.fio }), h("div", { class: "sub", text: `${r.status || "анкета не заполнена"}${r.rewarded ? ` · награда выдана ${r.rewarded}` : ""}` }))));
    }

    // --- достижения
    const achTitle = h("input", { class: "input", type: "text", placeholder: "Название знака", maxlength: "80" });
    const achDesc = h("input", { class: "input", type: "text", placeholder: "Описание (необязательно)", maxlength: "200" });
    const achievements = d.achievements.map((a) => h(
      "div", { class: "list-row" },
      h("div", { class: "main" }, a.title, h("div", { class: "sub", text: [a.description, a.date].filter(Boolean).join(" · ") })),
      h("button", {
        class: "btn btn-sm btn-ghost", type: "button", text: "Убрать",
        onclick: async (e) => {
          const ok = await run(e.currentTarget, () => api(`/users/${tid}/achievements`, { method: "DELETE", json: { title: a.title, date: a.date } }), "Знак убран");
          if (ok) route();
        },
      }),
    ));

    ctx.view(
      h("div", { class: "toolbar" }, h("a", { class: "btn btn-sm btn-ghost", href: "#/users", text: "← Все люди" })),
      h("div", { class: "user-head" },
        h("div", {}, avatar(u, true)),
        h("div", {},
          h("h1", { text: u.fio || "(без имени)" }),
          h("div", { class: "page-actions", style: "margin-top:8px" },
            tierBadge(u.tier, u.status || "—"),
            u.username ? h("a", { href: `https://t.me/${encodeURIComponent(u.username)}`, target: "_blank", rel: "noopener noreferrer", text: "@" + u.username }) : h("span", { class: "muted", text: "без username" }),
            h("span", { class: "muted", text: `ID ${tid}` }),
          ),
        ),
        h("div", { class: "spacer" }),
        h("div", {}, fileInput, h("button", { class: "btn btn-sm", type: "button", text: "Сменить фото", onclick: () => fileInput.click() })),
      ),
      h("div", { class: "grid grid-main" },
        h("div", {},
          h("div", { class: "card" }, h("h2", {}, "Статус"),
            h("div", { class: "toolbar", style: "margin:0" }, statusSelect, statusBtn),
            h("p", { class: "hint", style: "margin:10px 0 0", text: "«Нерезидент» — анкету одобрили, «резидент» — подписка оплачена. При одобрении пригласившему автоматически начисляется награда (один раз)." }),
          ),
          h("div", { class: "card" }, h("h2", {}, "Анкета"),
            h("div", { class: "field-row" }, formFields.slice(0, 2)),
            formFields.slice(2),
            h("div", { class: "modal-actions", style: "justify-content:flex-start" }, saveBtn),
          ),
          h("div", { class: "card" }, h("h2", {}, "Записи на события", h("span", { class: "count", text: d.signups.length || "" })), signups),
        ),
        h("div", {},
          h("div", { class: "card" }, h("h2", {}, "Дубики"),
            h("div", { class: "big-balance", text: num(u.balance) }),
            h("div", { class: "hint", style: "margin:4px 0 14px", text: "1 дубик = 1 ₽. Минус — списать." }),
            h("div", { class: "field-row" }, amount, reason),
            h("div", { class: "modal-actions", style: "justify-content:flex-start;margin:6px 0 12px" }, pointsBtn),
            ledger,
          ),
          h("div", { class: "card" }, h("h2", {}, "Рефералы"), refs),
          h("div", { class: "card" }, h("h2", {}, "Знаки Ордена"),
            achievements.length ? achievements : h("div", { class: "muted", style: "margin-bottom:12px", text: "Знаков пока нет" }),
            h("div", { class: "field-row", style: "margin-top:12px" }, achTitle, achDesc),
            h("button", {
              class: "btn btn-sm", type: "button", text: "Добавить знак",
              onclick: async (e) => {
                const ok = await run(e.currentTarget, () => api(`/users/${tid}/achievements`, { method: "POST", json: { title: achTitle.value, description: achDesc.value } }), "Знак добавлен");
                if (ok) route();
              },
            }),
          ),
          h("div", { class: "card" }, h("h2", {}, "Служебное"),
            h("dl", { class: "kv" },
              h("dt", { text: "Заявка подана" }), h("dd", { text: u.registered || "—" }),
              h("dt", { text: "Согласие на ПДн" }), h("dd", { text: u.consent || "не зафиксировано" }),
              h("dt", { text: "sb_id (Salebot)" }), h("dd", { text: d.sb_id || "—" }),
              h("dt", { text: "Доход" }), h("dd", { text: u.income || "—" }),
            ),
            h("div", { style: "margin-top:16px" },
              h("button", {
                class: "btn btn-sm btn-danger", type: "button", text: "Удалить анкету",
                onclick: async () => {
                  if (!(await confirmBox(`Удалить анкету «${u.fio}» из таблицы? Записи и дубики останутся, но человек пропадёт из списков и сможет подать заявку заново.`, { danger: true, confirmText: "Удалить" }))) return;
                  const ok = await run(null, () => api(`/users/${tid}`, { method: "DELETE" }), "Анкета удалена");
                  if (ok) location.hash = "#/users";
                },
              }),
            ),
          ),
        ),
      ),
    );
  }

  // ------------------------------------------------------------------- events

  function priceText(e) {
    if (!e.price && !e.price_nonresident) return h("span", { class: "muted", text: "не указана" });
    if (e.free) return h("span", { class: "badge badge-free", text: "бесплатно" });
    return [e.price || "—", h("span", { class: "sub", text: `нерезидент: ${e.price_nonresident || "как у резидента"}` })];
  }

  async function pageEvents(ctx) {
    const data = await api("/events");
    const all = data.events;
    const holder = h("div", {});
    const segment = h("div", { class: "segment" });

    const renderTable = () => {
      let list = all;
      if (state.eventsSeg === "upcoming") list = all.filter((e) => !e.past).sort((a, b) => (a.date > b.date ? 1 : -1));
      else if (state.eventsSeg === "past") list = all.filter((e) => e.past);
      holder.replaceChildren(table(
        [
          { label: "", render: (e) => (e.photo ? h("img", { class: "thumb", src: e.photo, alt: "", loading: "lazy" }) : h("div", { class: "thumb" })) },
          { label: "Дата", cls: "nowrap", render: (e) => [dateLabel(e.date), e.time ? h("span", { class: "sub", text: e.time }) : null] },
          { label: "Событие", render: (e) => [e.title, e.place ? h("span", { class: "sub", text: e.place }) : null] },
          { label: "Цена", render: priceText },
          { label: "Записано", cls: "num", render: (e) => `${e.people} чел. / ${e.tickets} бил.` },
          { label: "Деньгами", cls: "num", render: (e) => (e.cash ? money(e.cash) : "—") },
          {
            label: "", cls: "nowrap",
            render: (e) => h("div", { class: "page-actions" },
              h("a", { class: "btn btn-sm", href: `#/events/${e.id}/signups`, text: "Записавшиеся" }),
              h("button", { class: "btn btn-sm", type: "button", text: "Изменить", onclick: () => openEventForm(e) }),
              h("button", { class: "btn btn-sm btn-ghost", type: "button", text: "Копия", title: "Новое событие на основе этого (без даты)", onclick: () => openEventForm(null, e) }),
            ),
          },
        ],
        list,
        { empty: "Событий нет", onRow: (e) => { location.hash = `#/events/${e.id}/signups`; } },
      ));
    };
    const segs = [["upcoming", "Предстоящие"], ["past", "Прошедшие"], ["all", "Все"]];
    const renderSegment = () => segment.replaceChildren(...segs.map(([key, label]) => h(
      "button", { type: "button", class: state.eventsSeg === key ? "active" : "", onclick: () => { state.eventsSeg = key; renderSegment(); renderTable(); } },
      label, h("span", { class: "n", text: key === "all" ? all.length : all.filter((e) => (key === "past") === e.past).length }),
    )));
    renderSegment();
    renderTable();

    ctx.view(
      pageHead("Афиша", "События, цены и обложки — то, что видят в мини-аппе",
        h("button", { class: "btn btn-primary", type: "button", text: "+ Добавить событие", onclick: () => openEventForm(null) })),
      h("div", { class: "toolbar" }, segment),
      holder,
    );
  }

  function openEventForm(ev, template) {
    const isNew = !ev;
    const empty = { title: "", description: "", date: "", time: "", place: "", price: "", price_nonresident: "", photo: "", photo_dark: "" };
    // template — «Копия»: всё как у образца, кроме даты (её вводят заново)
    const e = ev || (template ? { ...template, date: "" } : empty);

    const f = {
      title: h("input", { type: "text", value: e.title, maxlength: "120", placeholder: "Например: Бизнес-завтрак Банного Ордена" }),
      description: h("textarea", { value: e.description, maxlength: "1000", placeholder: "Короткое описание (показывается на странице события)" }),
      date: h("input", { type: "date", value: e.date }),
      time: h("input", { type: "text", value: e.time, maxlength: "40", placeholder: "10:30–13:30" }),
      place: h("input", { type: "text", value: e.place, maxlength: "160", placeholder: "Ресторан, адрес или Zoom" }),
      price: h("input", { type: "text", value: e.price, placeholder: "15000 или Бесплатно" }),
      price_nonresident: h("input", { type: "text", value: e.price_nonresident, placeholder: "пусто = как у резидента" }),
      photo: h("input", { type: "text", value: e.photo, placeholder: "/static/…" }),
      photo_dark: h("input", { type: "text", value: e.photo_dark, placeholder: "/static/… (если пусто — берётся обычное фото)" }),
    };

    const previewLight = h("img", { class: "thumb-lg", alt: "" });
    const previewDark = h("img", { class: "thumb-lg", alt: "" });
    const refreshPreview = () => {
      previewLight.src = f.photo.value || "data:,";
      previewDark.src = f.photo_dark.value || f.photo.value || "data:,";
    };
    f.photo.addEventListener("input", refreshPreview);
    f.photo_dark.addEventListener("input", refreshPreview);
    refreshPreview();

    const modeSelect = h("select", { class: "input input-select", style: "max-width:330px" },
      h("option", { value: "cover", text: "Фото — обрезать до 2:1, тёмная версия автоматически" }),
      h("option", { value: "poster", text: "Постер с текстом — без обрезки (16:9), тёмная автоматически" }),
      h("option", { value: "light", text: "Заменить только светлую" }),
      h("option", { value: "dark", text: "Заменить только тёмную (готовую)" }),
    );
    const fileInput = h("input", {
      type: "file", accept: "image/*", hidden: true,
      onchange: async (ev2) => {
        const file = ev2.target.files[0];
        ev2.target.value = "";
        if (!file) return;
        const form = new FormData();
        form.append("file", file);
        form.append("mode", modeSelect.value);
        const result = await run(null, () => api("/upload/event-cover", { method: "POST", form }), "Фото загружено");
        if (result && result.photo) f.photo.value = result.photo;
        if (result && result.photo_dark) f.photo_dark.value = result.photo_dark;
        refreshPreview();
      },
    });

    let modal;
    const saveBtn = h("button", {
      class: "btn btn-primary", type: "button", text: isNew ? "Создать событие" : "Сохранить",
      onclick: async (evt) => {
        const payload = {};
        for (const [k, el] of Object.entries(f)) payload[k] = el.value;
        const ok = await run(evt.currentTarget, () => api(isNew ? "/events" : `/events/${e.id}`, { method: isNew ? "POST" : "PUT", json: payload }), isNew ? "Событие создано" : "Событие сохранено");
        if (ok) { modal.close(); route(); }
      },
    });

    const body = h(
      "div", {},
      field("Название", f.title),
      field("Описание", f.description),
      h("div", { class: "field-row" }, field("Дата", f.date), field("Время", f.time, "Свободный текст: 18:00 или 10:30–13:30")),
      field("Место", f.place),
      h("div", { class: "field-row" },
        field("Цена для резидента", f.price, "Число, «Бесплатно» или пусто"),
        field("Цена для нерезидента", f.price_nonresident, "Пусто — как у резидента"),
      ),
      h("div", { class: "card", style: "padding:14px 16px" },
        h("h2", {}, "Обложка"),
        h("div", { class: "cover-box" },
          h("figure", {}, previewLight, h("figcaption", { text: "Светлая — Афиша и страница события" })),
          h("figure", {}, previewDark, h("figcaption", { text: "Тёмная — карточка «Ближайшее событие» на Главной" })),
        ),
        h("div", { class: "upload-row" }, modeSelect, fileInput, h("button", { class: "btn btn-sm", type: "button", text: "Выбрать файл…", onclick: () => fileInput.click() })),
        h("div", { class: "field-row" }, field("Ссылка на светлую", f.photo), field("Ссылка на тёмную", f.photo_dark)),
        h("p", { class: "hint", style: "margin:0", text: "Лучший размер — 1600×800 (2:1). Главное (лица, текст) держите в центральной полосе: на карточке афиши видна лента ≈3:1." }),
      ),
      h("div", { class: "modal-actions" },
        !isNew ? h("button", {
          class: "btn btn-danger", type: "button", style: "margin-right:auto", text: "Удалить",
          onclick: async () => {
            if (!(await confirmBox(`Удалить событие «${e.title}»? Это возможно, только если на него никто не записан.`, { danger: true, confirmText: "Удалить" }))) return;
            const ok = await run(null, () => api(`/events/${e.id}`, { method: "DELETE" }), "Событие удалено");
            if (ok) { modal.close(); route(); }
          },
        }) : null,
        h("button", { class: "btn btn-ghost", type: "button", text: "Отмена", onclick: () => modal.close() }),
        saveBtn,
      ),
    );
    modal = openModal(isNew ? (template ? "Новое событие (копия)" : "Новое событие") : `Событие #${e.id}`, body, { wide: true });
  }

  async function pageEventSignups(ctx, eventId) {
    const [evData, sData] = await Promise.all([api("/events"), api(`/events/${encodeURIComponent(eventId)}/signups`)]);
    const ev = evData.events.find((x) => String(x.id) === String(eventId));
    if (!ev) throw new Error("Событие не найдено");
    const rows = sData.signups;
    const paid = rows.filter((r) => r.status === "оплачено");
    const people = paid.length;
    const tickets = paid.reduce((s, r) => s + r.quantity, 0);
    const cash = paid.reduce((s, r) => s + r.cash, 0);
    const points = paid.reduce((s, r) => s + r.points, 0);

    const tbl = table(
      [
        { label: "Человек", render: (r) => h("div", {}, h("a", { href: `#/users/${r.telegram_id}`, text: r.fio }), h("span", { class: "sub", text: [r.username ? "@" + r.username : "", TIER[r.tier]].filter(Boolean).join(" · ") })) },
        { label: "Телефон", cls: "nowrap", render: (r) => r.phone || "—" },
        { label: "Запись", render: (r) => signupBadge(r.status) },
        { label: "Билетов", cls: "num", render: (r) => r.quantity },
        {
          label: "Оплата",
          render: (r) => (r.cash || r.points || r.promo
            ? [r.cash ? money(r.cash) : null, r.points ? h("span", { class: "sub", text: `дубиков: ${num(r.points)}` }) : null, r.promo ? h("span", { class: "sub", text: `промокод ${r.promo}` }) : null]
            : "—"),
        },
        { label: "Когда", cls: "nowrap", render: (r) => r.created || "—" },
        {
          label: "", render: (r) => (r.status === "отклонено" ? "" : h("button", {
            class: "btn btn-sm btn-danger", type: "button", text: "Отменить",
            onclick: async (e) => {
              const btn = e.currentTarget;
              const note = r.cash ? ` Деньги (${money(r.cash)}) придётся вернуть вручную в кабинете Продамуса.` : "";
              if (!(await confirmBox(`Отменить запись «${r.fio}»? Списанные дубики вернутся на баланс.${note}`, { danger: true, confirmText: "Отменить запись" }))) return;
              const ok = await run(btn, () => api(`/events/${ev.id}/signups/${r.telegram_id}`, { method: "DELETE" }), "Запись отменена");
              if (ok) route();
            },
          })),
        },
      ],
      rows,
      { empty: "Пока никто не записался" },
    );

    ctx.view(
      h("div", { class: "toolbar" }, h("a", { class: "btn btn-sm btn-ghost", href: "#/events", text: "← Афиша" })),
      pageHead(ev.title, `${dateLabel(ev.date)}${ev.time ? " · " + ev.time : ""}${ev.place ? " · " + ev.place : ""}`, [
        h("a", { class: "btn", href: `/admin/api/events/${encodeURIComponent(ev.id)}/export.csv`, text: "Экспорт CSV" }),
        h("button", { class: "btn", type: "button", text: "Изменить событие", onclick: () => openEventForm(ev) }),
        h("button", { class: "btn btn-primary", type: "button", text: "+ Записать человека", onclick: () => openAddSignup(ev) }),
      ]),
      h("div", { class: "grid grid-4", style: "margin-bottom:18px" },
        h("div", { class: "stat" }, h("div", { class: "label", text: "Записано людей" }), h("div", { class: "value", text: people })),
        h("div", { class: "stat" }, h("div", { class: "label", text: "Билетов" }), h("div", { class: "value", text: tickets })),
        h("div", { class: "stat" }, h("div", { class: "label", text: "Оплачено деньгами" }), h("div", { class: "value", text: money(cash) })),
        h("div", { class: "stat" }, h("div", { class: "label", text: "Оплачено дубиками" }), h("div", { class: "value", text: num(points) })),
      ),
      tbl,
    );
  }

  async function openAddSignup(ev) {
    if (!state.users.length) state.users = (await api("/users")).users;
    const search = h("input", { class: "input", type: "search", placeholder: "Найти человека по имени, телефону, @username…" });
    const qty = h("input", { class: "input", type: "number", min: "1", max: "20", value: "1", style: "max-width:110px" });
    const results = h("div", {});
    let chosen = null;
    let modal;
    const chosenBox = h("div", { class: "hint", text: "Выберите человека из списка" });
    const addBtn = h("button", {
      class: "btn btn-primary", type: "button", text: "Записать", disabled: true,
      onclick: async (e) => {
        const ok = await run(e.currentTarget, () => api(`/events/${ev.id}/signups`, { method: "POST", json: { telegram_id: chosen.telegram_id, quantity: qty.value } }), `${chosen.fio} записан(а)`);
        if (ok) { modal.close(); route(); }
      },
    });
    const renderResults = () => {
      const q = search.value.trim().toLowerCase();
      const list = state.users
        .filter((u) => !q || [u.fio, u.phone, u.username, u.company, u.telegram_id].some((v) => (v || "").toLowerCase().includes(q)))
        .slice(0, 8);
      results.replaceChildren(...list.map((u) => h(
        "div", {
          class: "list-row", style: "cursor:pointer",
          onclick: () => {
            chosen = u;
            chosenBox.textContent = `Выбран: ${u.fio} (${TIER[u.tier]})`;
            addBtn.disabled = false;
          },
        },
        personCell(u), tierBadge(u.tier),
      )));
      if (!list.length) results.replaceChildren(h("div", { class: "muted", text: "Никого не нашлось" }));
    };
    search.addEventListener("input", renderResults);
    renderResults();
    modal = openModal(`Записать на «${ev.title}»`, h(
      "div", {},
      h("p", { class: "hint", text: "Запись создаётся сразу как оплаченная (например, человек заплатил переводом). Продамус не используется." }),
      search, results,
      h("div", { style: "margin:14px 0" }, chosenBox),
      field("Билетов", qty),
      h("div", { class: "modal-actions" }, h("button", { class: "btn btn-ghost", type: "button", text: "Отмена", onclick: () => modal.close() }), addBtn),
    ));
  }

  // -------------------------------------------------------------------- promo

  async function pagePromo(ctx) {
    const data = await api("/promo");
    const tbl = table(
      [
        { label: "Код", render: (p) => h("strong", { text: p.code }) },
        { label: "Скидка", render: (p) => `${p.size}${p.type === "процент" ? " %" : " ₽"}` },
        { label: "События", render: (p) => p.events },
        { label: "Использовано", cls: "num", render: (p) => `${p.uses}${p.limit ? " / " + p.limit : ""}` },
        { label: "Действует до", cls: "nowrap", render: (p) => p.until || "бессрочно" },
        { label: "Статус", render: (p) => h("span", { class: `badge ${p.active ? "badge-paid" : "badge-past"}`, text: p.active ? "включён" : "выключен" }) },
        {
          label: "", cls: "nowrap",
          render: (p) => h("div", { class: "page-actions" },
            h("button", { class: "btn btn-sm", type: "button", text: p.active ? "Выключить" : "Включить", onclick: async (e) => {
              const ok = await run(e.currentTarget, () => api(`/promo/${encodeURIComponent(p.code)}`, { method: "PUT", json: { type: p.type, size: p.size, events: p.events, limit: p.limit, until: p.until, active: !p.active } }), p.active ? "Код выключен" : "Код включён");
              if (ok) route();
            } }),
            h("button", { class: "btn btn-sm", type: "button", text: "Изменить", onclick: () => openPromoForm(p) }),
          ),
        },
      ],
      data.promos,
      { empty: "Промокодов пока нет" },
    );
    ctx.view(
      pageHead("Промокоды", "Скидка на оплату события; вводится в форме оплаты в мини-аппе",
        h("button", { class: "btn btn-primary", type: "button", text: "+ Новый промокод", onclick: () => openPromoForm(null) })),
      tbl,
    );
  }

  function openPromoForm(p) {
    const isNew = !p;
    const f = {
      code: h("input", { type: "text", value: p ? p.code : "", maxlength: "32", disabled: !isNew, placeholder: "SPRING2026" }),
      type: h("select", { class: "input-select", value: p ? p.type : "процент" }, h("option", { value: "процент", text: "Процент от суммы" }), h("option", { value: "рубли", text: "Рубли (на весь заказ)" })),
      size: h("input", { type: "number", min: "1", step: "1", value: p ? p.size : "", placeholder: "10" }),
      events: h("input", { type: "text", value: p ? p.events : "все", placeholder: "все или ID через запятую: 11, 12" }),
      limit: h("input", { type: "number", min: "1", step: "1", value: p ? p.limit : "", placeholder: "без ограничений" }),
      until: h("input", { type: "date", value: p ? p.until : "" }),
    };
    const active = h("input", { type: "checkbox", checked: p ? p.active : true });
    let modal;
    const body = h(
      "div", {},
      field("Код", f.code, isNew ? "Буквы, цифры, «-» и «_». Регистр при вводе не важен." : "Код менять нельзя — создайте новый"),
      h("div", { class: "field-row" }, field("Тип скидки", f.type), field("Размер", f.size, "Процент (1–100) или рубли")),
      field("На какие события", f.events, "«все» — на любые, включая будущие; или ID событий из раздела «Афиша»"),
      h("div", { class: "field-row" }, field("Лимит применений", f.limit, "Сколько раз всего"), field("Действует до", f.until, "Включительно; пусто — бессрочно")),
      h("label", { class: "checkbox" }, active, h("span", { text: "Код включён" })),
      h("div", { class: "modal-actions" },
        !isNew ? h("button", {
          class: "btn btn-danger", type: "button", style: "margin-right:auto", text: "Удалить",
          onclick: async () => {
            if (!(await confirmBox(`Удалить промокод ${p.code}? Уже оформленные записи останутся.`, { danger: true, confirmText: "Удалить" }))) return;
            const ok = await run(null, () => api(`/promo/${encodeURIComponent(p.code)}`, { method: "DELETE" }), "Код удалён");
            if (ok) { modal.close(); route(); }
          },
        }) : null,
        h("button", { class: "btn btn-ghost", type: "button", text: "Отмена", onclick: () => modal.close() }),
        h("button", {
          class: "btn btn-primary", type: "button", text: isNew ? "Создать" : "Сохранить",
          onclick: async (e) => {
            const payload = { code: f.code.value, type: f.type.value, size: f.size.value, events: f.events.value, limit: f.limit.value, until: f.until.value, active: active.checked };
            const ok = await run(e.currentTarget, () => api(isNew ? "/promo" : `/promo/${encodeURIComponent(p.code)}`, { method: isNew ? "POST" : "PUT", json: payload }), isNew ? "Код создан" : "Код сохранён");
            if (ok) { modal.close(); route(); }
          },
        }),
      ),
    );
    modal = openModal(isNew ? "Новый промокод" : `Промокод ${p.code}`, body);
  }

  // ---------------------------------------------------------------- materials

  async function pageMaterials(ctx) {
    const data = await api("/materials");
    const tbl = table(
      [
        { label: "", render: (m) => (m.photo ? h("img", { class: "thumb", src: m.photo, alt: "", loading: "lazy" }) : h("div", { class: "thumb" })) },
        { label: "Название", render: (m) => [m.title, m.description ? h("span", { class: "sub", text: m.description }) : null] },
        { label: "Категория", render: (m) => m.category || "—" },
        { label: "Дата", cls: "nowrap", render: (m) => m.date || "—" },
        { label: "Ссылка", render: (m) => (m.link ? h("a", { href: m.link, target: "_blank", rel: "noopener noreferrer", text: "Открыть" }) : "—") },
        { label: "", render: (m) => h("button", { class: "btn btn-sm", type: "button", text: "Изменить", onclick: () => openMaterialForm(m) }) },
      ],
      data.materials,
      { empty: "Материалов пока нет" },
    );
    ctx.view(
      pageHead("Материалы", "Библиотека для резидентов (видео, записи эфиров)",
        h("button", { class: "btn btn-primary", type: "button", text: "+ Добавить материал", onclick: () => openMaterialForm(null) })),
      h("div", { class: "notice", text: "Материал с обложкой показывается в мини-аппе одной картинкой без текста — название и подписи лучше размещать на самом постере (16:9)." }),
      tbl,
    );
  }

  function openMaterialForm(m) {
    const isNew = !m;
    const f = {
      title: h("input", { type: "text", value: m ? m.title : "", maxlength: "150" }),
      description: h("textarea", { value: m ? m.description : "", maxlength: "600" }),
      link: h("input", { type: "text", value: m ? m.link : "", placeholder: "https://www.youtube.com/watch?v=…" }),
      category: h("input", { type: "text", value: m ? m.category : "", maxlength: "60", placeholder: "Честный разговор" }),
      date: h("input", { type: "date", value: m ? m.date : "" }),
      photo: h("input", { type: "text", value: m ? m.photo : "", placeholder: "/static/…" }),
    };
    const preview = h("img", { class: "thumb-lg", style: "aspect-ratio:16/9;max-width:340px", alt: "" });
    const refresh = () => { preview.src = f.photo.value || "data:,"; };
    f.photo.addEventListener("input", refresh);
    refresh();
    const fileInput = h("input", {
      type: "file", accept: "image/*", hidden: true,
      onchange: async (ev) => {
        const file = ev.target.files[0];
        ev.target.value = "";
        if (!file) return;
        const form = new FormData();
        form.append("file", file);
        const r = await run(null, () => api("/upload/material-cover", { method: "POST", form }), "Обложка загружена");
        if (r && r.photo) { f.photo.value = r.photo; refresh(); }
      },
    });
    let modal;
    const body = h(
      "div", {},
      field("Название", f.title),
      field("Описание", f.description),
      field("Ссылка на видео/материал", f.link),
      h("div", { class: "field-row" }, field("Категория", f.category), field("Дата публикации", f.date)),
      h("div", { class: "card", style: "padding:14px 16px" },
        h("h2", {}, "Обложка (16:9)"),
        preview,
        h("div", { class: "upload-row", style: "margin-top:12px" }, fileInput, h("button", { class: "btn btn-sm", type: "button", text: "Загрузить файл…", onclick: () => fileInput.click() })),
        field("Ссылка на обложку", f.photo),
      ),
      h("div", { class: "modal-actions" },
        !isNew ? h("button", {
          class: "btn btn-danger", type: "button", style: "margin-right:auto", text: "Удалить",
          onclick: async () => {
            if (!(await confirmBox(`Удалить материал «${m.title}»?`, { danger: true, confirmText: "Удалить" }))) return;
            const ok = await run(null, () => api(`/materials/${m.row}`, { method: "DELETE", json: { expect_title: m.title } }), "Материал удалён");
            if (ok) { modal.close(); route(); }
          },
        }) : null,
        h("button", { class: "btn btn-ghost", type: "button", text: "Отмена", onclick: () => modal.close() }),
        h("button", {
          class: "btn btn-primary", type: "button", text: isNew ? "Добавить" : "Сохранить",
          onclick: async (e) => {
            const payload = {};
            for (const [k, el] of Object.entries(f)) payload[k] = el.value;
            if (!isNew) payload.expect_title = m.title;
            const ok = await run(e.currentTarget, () => api(isNew ? "/materials" : `/materials/${m.row}`, { method: isNew ? "POST" : "PUT", json: payload }), isNew ? "Материал добавлен" : "Материал сохранён");
            if (ok) { modal.close(); route(); }
          },
        }),
      ),
    );
    modal = openModal(isNew ? "Новый материал" : "Материал", body, { wide: true });
  }

  // ------------------------------------------------------------ points + log

  async function pagePoints(ctx) {
    const d = await api("/points");
    ctx.view(
      pageHead("Дубики", `В обороте: ${num(d.total)} (сумма положительных балансов). Начислить или списать — в карточке человека.`),
      table(
        [
          { label: "Дата", cls: "nowrap", render: (i) => i.date || "—" },
          { label: "Человек", render: (i) => h("a", { href: `#/users/${i.telegram_id}`, text: i.fio }) },
          { label: "Сумма", cls: "num", render: (i) => h("strong", { class: i.amount > 0 ? "plus" : "minus", text: `${i.amount > 0 ? "+" : "−"}${num(Math.abs(i.amount))}` }) },
          { label: "Причина", render: (i) => i.reason || "—" },
          { label: "Ссылка", render: (i) => h("span", { class: "muted", text: i.ref || "" }) },
        ],
        d.items,
        { empty: "Операций пока не было" },
      ),
    );
  }

  async function pageLog(ctx) {
    const d = await api("/log");
    ctx.view(
      pageHead("Журнал действий", "Кто и что менял в панели (последние 300 записей)"),
      table(
        [
          { label: "Время", cls: "nowrap", render: (i) => i.time },
          { label: "Админ", render: (i) => i.admin },
          { label: "Действие", render: (i) => h("strong", { text: i.action }) },
          { label: "Объект", render: (i) => i.target || "—" },
          { label: "Детали", render: (i) => h("span", { class: "muted", text: i.details || "" }) },
        ],
        d.items,
        { empty: "Журнал пуст" },
      ),
    );
  }

  // ------------------------------------------------------------------- router

  const NAV = [
    { key: "dashboard", href: "#/dashboard", label: "Обзор", icon: "dashboard" },
    { key: "users", href: "#/users", label: "Люди", icon: "users", badge: true },
    { key: "events", href: "#/events", label: "Афиша", icon: "calendar" },
    { key: "promo", href: "#/promo", label: "Промокоды", icon: "tag" },
    { key: "materials", href: "#/materials", label: "Материалы", icon: "book" },
    { key: "points", href: "#/points", label: "Дубики", icon: "coin" },
    { key: "log", href: "#/log", label: "Журнал", icon: "log" },
  ];

  const ROUTES = [
    { re: /^#\/dashboard$/, nav: "dashboard", render: (ctx) => pageDashboard(ctx) },
    { re: /^#\/users(?:\?(.*))?$/, nav: "users", render: (ctx, m) => pageUsers(ctx, m[1]) },
    { re: /^#\/users\/([^/?]+)$/, nav: "users", render: (ctx, m) => pageUser(ctx, decodeURIComponent(m[1])) },
    { re: /^#\/events$/, nav: "events", render: (ctx) => pageEvents(ctx) },
    { re: /^#\/events\/([^/]+)\/signups$/, nav: "events", render: (ctx, m) => pageEventSignups(ctx, decodeURIComponent(m[1])) },
    { re: /^#\/promo$/, nav: "promo", render: (ctx) => pagePromo(ctx) },
    { re: /^#\/materials$/, nav: "materials", render: (ctx) => pageMaterials(ctx) },
    { re: /^#\/points$/, nav: "points", render: (ctx) => pagePoints(ctx) },
    { re: /^#\/log$/, nav: "log", render: (ctx) => pageLog(ctx) },
  ];

  function buildNav() {
    const nav = document.getElementById("nav");
    nav.replaceChildren(...NAV.map((n) => h(
      "a", { href: n.href, "data-nav": n.key },
      icon(n.icon), n.label,
      n.badge ? h("span", { class: "badge-count", id: "pending-count", hidden: true, title: "Заявок на рассмотрении" }) : null,
    )));
  }

  function markNav(key) {
    for (const a of document.querySelectorAll("#nav a")) a.classList.toggle("active", a.dataset.nav === key);
  }

  async function route() {
    const hash = location.hash || "#/dashboard";
    const seq = ++renderSeq;
    let matched = null;
    for (const r of ROUTES) {
      const m = r.re.exec(hash);
      if (m) { matched = { r, m }; break; }
    }
    if (!matched) { location.hash = "#/dashboard"; return; }
    markNav(matched.r.nav);
    // при смене страницы закрываем открытые модальные окна
    document.getElementById("modal-root").replaceChildren();
    view.replaceChildren(h("div", { class: "loading", text: "Загрузка…" }));
    const ctx = { view: (...nodes) => { if (seq === renderSeq) setView(...nodes); } };
    try {
      await matched.r.render(ctx, matched.m);
    } catch (err) {
      if (seq !== renderSeq) return;
      setView(h("div", { class: "card" }, h("h2", {}, "Не получилось загрузить"), h("p", { text: err.message }), h("button", { class: "btn", type: "button", text: "Повторить", onclick: () => route() })));
    }
  }

  async function init() {
    try {
      const me = await api("/me");
      state.csrf = me.csrf;
      state.login = me.login;
    } catch (err) {
      return; // 401 уже перенаправил на страницу входа
    }
    document.getElementById("whoami").textContent = state.login;
    buildNav();
    window.addEventListener("hashchange", route);
    route();
  }

  init();
})();
