/* Portal zivotnich situaci MC Praha 13 - jednoduchy frontend bez frameworku.
   Zadne localStorage, zadne prihlasovani. Stav drzi URL (hash). */

var LANGS = ["cs", "uk", "ru"];
var lang = "cs";
var state = { query: "", audience: "", situations: [], loaded: false };

var I18N = {
  cs: {
    skip: "Přejít na obsah",
    brandTitle: "Portál životních situací",
    brandSub: "Městská část Praha 13 — prototyp",
    listTitle: "Vyberte svou životní situaci",
    listLead: "Dostanete seznam kroků: co udělat, do kdy, kam jít a jaké doklady si vzít.",
    searchLabel: "Hledat situaci",
    searchPlaceholder: "Hledat (např. pes, škola, pobyt)",
    filterAll: "Vše", filterCitizen: "Občan", filterForeigner: "Cizinec",
    noResults: "Nic nenalezeno. Zkuste jiné slovo.",
    back: "← Zpět na přehled",
    katalogTitle: "Související služby z Katalogu služeb veřejné správy",
    p13Title: "Údaje stažené ze stránky MČ Praha 13",
    p13Dept: "Útvar", p13Address: "Kde", p13Hours: "Úřední hodiny",
    p13Responsible: "Za správnost popisu odpovídá",
    p13Fetched: "Staženo parserem dne ",
    p13RawDeadline: "Text o lhůtách ze stránky (zatím neověřený, do kroků se nepřepisuje): ",
    footerData: "Data: Katalog služeb veřejné správy (CC BY 4.0), stránky „Jak si zařídit“ MČ Praha 13, Sbírka zákonů.",
    footerWarn: "Prototyp pro ideathon. Nejde o závazné právní stanovisko. Neověřené lhůty jsou označené.",
    count: "Zobrazeno situací: ",
    steps: "kroků",
    todoBadge: "lhůta k ověření",
    audienceAll: "pro všechny", audienceCitizen: "občan", audienceForeigner: "cizinec",
    deadlineLabel: "Lhůta",
    deadlineTodo: "Lhůta zatím není ověřena",
    deadlineNA: "Lhůta se v tomto kroku neuplatní",
    verifyHint: "Kde ji dohledat: ",
    source: "Zdroj: ",
    authority: "Kdo to řeší",
    where: "Kde",
    hours: "Úřední hodiny",
    documents: "Doklady s sebou",
    sanction: "Co hrozí, když to nestihnete",
    sanctionUnknown: "Sankce není v dostupných zdrojích uvedena — je potřeba ji ověřit.",
    sourceLink: "Zdroj kroku",
    noSourceUrl: "Bez odkazu na zdroj — položka čeká na ruční ověření.",
    legend: "Kroky s oranžovým okrajem mají neověřenou lhůtu. Prototyp lhůty nedomýšlí — raději je nechá prázdné.",
    fallback: "Některé texty jsou zatím jen v češtině.",
    loading: "Načítám…",
    error: "Data se nepodařilo načíst. Běží server (python app.py)?",
    notFound: "Taková situace tu není."
  },
  uk: {
    skip: "Перейти до змісту",
    brandTitle: "Портал життєвих ситуацій",
    brandSub: "Міський район Прага 13 — прототип",
    listTitle: "Оберіть свою життєву ситуацію",
    listLead: "Отримаєте перелік кроків: що зробити, до якого строку, куди йти та які документи взяти.",
    searchLabel: "Пошук ситуації",
    searchPlaceholder: "Пошук (напр. собака, школа, перебування)",
    filterAll: "Усі", filterCitizen: "Громадянин", filterForeigner: "Іноземець",
    noResults: "Нічого не знайдено. Спробуйте інше слово.",
    back: "← Назад до переліку",
    katalogTitle: "Пов'язані послуги з Каталогу послуг державного управління",
    p13Title: "Дані, завантажені зі сторінки МЧ Прага 13",
    p13Dept: "Відділ", p13Address: "Де", p13Hours: "Години прийому",
    p13Responsible: "За правильність опису відповідає",
    p13Fetched: "Завантажено парсером ",
    p13RawDeadline: "Текст про строки зі сторінки (ще не перевірений, у кроки не переноситься): ",
    footerData: "Дані: Каталог послуг державного управління (CC BY 4.0), сторінки «Jak si zařídit» МЧ Прага 13, Збірник законів.",
    footerWarn: "Прототип для ідеатону. Це не є обов'язковим правовим висновком. Неперевірені строки позначені.",
    count: "Показано ситуацій: ",
    steps: "кроків",
    todoBadge: "строк не перевірено",
    audienceAll: "для всіх", audienceCitizen: "громадянин", audienceForeigner: "іноземець",
    deadlineLabel: "Строк",
    deadlineTodo: "Строк ще не перевірено (Lhůta zatím není ověřena)",
    deadlineNA: "У цьому кроці строк не застосовується",
    verifyHint: "Де перевірити: ",
    source: "Джерело: ",
    authority: "Хто вирішує",
    where: "Де",
    hours: "Години прийому",
    documents: "Документи з собою",
    sanction: "Що буде, якщо не встигнете",
    sanctionUnknown: "У доступних джерелах санкція не вказана — потрібно перевірити.",
    sourceLink: "Джерело кроку",
    noSourceUrl: "Без посилання на джерело — потребує ручної перевірки.",
    legend: "Кроки з помаранчевою рамкою мають неперевірений строк. Прототип строки не вигадує — краще залишає порожніми.",
    fallback: "Частина текстів наразі лише чеською мовою.",
    loading: "Завантаження…",
    error: "Не вдалося завантажити дані. Чи запущено сервер (python app.py)?",
    notFound: "Такої ситуації тут немає."
  },
  ru: {
    skip: "Перейти к содержанию",
    brandTitle: "Портал жизненных ситуаций",
    brandSub: "Городской район Прага 13 — прототип",
    listTitle: "Выберите свою жизненную ситуацию",
    listLead: "Получите список шагов: что сделать, к какому сроку, куда идти и какие документы взять.",
    searchLabel: "Поиск ситуации",
    searchPlaceholder: "Поиск (напр. собака, школа, пребывание)",
    filterAll: "Все", filterCitizen: "Гражданин", filterForeigner: "Иностранец",
    noResults: "Ничего не найдено. Попробуйте другое слово.",
    back: "← Назад к списку",
    katalogTitle: "Связанные услуги из Каталога услуг государственного управления",
    p13Title: "Данные, загруженные со страницы МЧ Прага 13",
    p13Dept: "Отдел", p13Address: "Где", p13Hours: "Часы приёма",
    p13Responsible: "За правильность описания отвечает",
    p13Fetched: "Загружено парсером ",
    p13RawDeadline: "Текст о сроках со страницы (пока не проверен, в шаги не переносится): ",
    footerData: "Данные: Каталог услуг государственного управления (CC BY 4.0), страницы «Jak si zařídit» МЧ Прага 13, Сборник законов.",
    footerWarn: "Прототип для идеатона. Это не обязательное правовое заключение. Непроверенные сроки отмечены.",
    count: "Показано ситуаций: ",
    steps: "шагов",
    todoBadge: "срок не проверен",
    audienceAll: "для всех", audienceCitizen: "гражданин", audienceForeigner: "иностранец",
    deadlineLabel: "Срок",
    deadlineTodo: "Срок пока не проверен (Lhůta zatím není ověřena)",
    deadlineNA: "В этом шаге срок не применяется",
    verifyHint: "Где проверить: ",
    source: "Источник: ",
    authority: "Кто решает",
    where: "Где",
    hours: "Часы приёма",
    documents: "Документы с собой",
    sanction: "Что будет, если не успеете",
    sanctionUnknown: "В доступных источниках санкция не указана — нужно проверить.",
    sourceLink: "Источник шага",
    noSourceUrl: "Без ссылки на источник — требует ручной проверки.",
    legend: "Шаги с оранжевой рамкой имеют непроверенный срок. Прототип сроки не выдумывает — лучше оставит пустыми.",
    fallback: "Часть текстов пока только на чешском языке.",
    loading: "Загрузка…",
    error: "Не удалось загрузить данные. Запущен ли сервер (python app.py)?",
    notFound: "Такой ситуации здесь нет."
  }
};

function t(key) { return (I18N[lang] && I18N[lang][key]) || I18N.cs[key] || key; }
function $(selector) { return document.querySelector(selector); }
function el(tag, className, text) {
  var node = document.createElement(tag);
  if (className) { node.className = className; }
  if (text !== undefined && text !== null) { node.textContent = text; }
  return node;
}

/* Preklad obsahu: kdyz chybi, padame na cestinu. Nikdy nic nevymyslime. */
function field(object, name, fallbackUsed) {
  var value = object[name + "_" + lang];
  if (value) { return value; }
  if (lang !== "cs" && object[name + "_cs"] && fallbackUsed) { fallbackUsed.hit = true; }
  return object[name + "_cs"] || "";
}

function applyStaticTexts() {
  document.documentElement.lang = lang;
  var nodes = document.querySelectorAll("[data-i18n]");
  for (var i = 0; i < nodes.length; i++) {
    nodes[i].textContent = t(nodes[i].getAttribute("data-i18n"));
  }
  var placeholders = document.querySelectorAll("[data-i18n-placeholder]");
  for (var j = 0; j < placeholders.length; j++) {
    placeholders[j].placeholder = t(placeholders[j].getAttribute("data-i18n-placeholder"));
  }
  var buttons = document.querySelectorAll(".lang-btn");
  for (var k = 0; k < buttons.length; k++) {
    buttons[k].setAttribute("aria-pressed", buttons[k].dataset.lang === lang ? "true" : "false");
  }
}

/* ---------------- obrazovka 1 ---------------- */

function audienceLabel(audience) {
  if (audience === "citizen") { return t("audienceCitizen"); }
  if (audience === "foreigner") { return t("audienceForeigner"); }
  return t("audienceAll");
}

function renderList() {
  var container = $("#cards");
  container.innerHTML = "";
  var fallback = { hit: false };
  var items = state.situations;

  for (var i = 0; i < items.length; i++) {
    var situation = items[i];
    var card = el("a", "card");
    card.href = "#/situace/" + situation.slug;
    card.appendChild(el("p", "eyebrow", situation.category || ""));
    card.appendChild(el("h2", null, field(situation, "title", fallback)));
    var summary = field(situation, "summary", fallback);
    if (summary) { card.appendChild(el("p", null, summary)); }

    var meta = el("div", "card-meta");
    meta.appendChild(el("span", "tag tag-audience", audienceLabel(situation.audience)));
    meta.appendChild(el("span", "tag", situation.step_count + " " + t("steps")));
    if (situation.manual_todo_count > 0) {
      meta.appendChild(el("span", "tag tag-todo",
        situation.manual_todo_count + "× " + t("todoBadge")));
    }
    card.appendChild(meta);
    container.appendChild(card);
  }

  $("#list-count").textContent = t("count") + items.length;
  $("#list-empty").hidden = items.length !== 0;
  var note = $("#list-note");
  note.textContent = t("fallback");
  note.hidden = !(fallback.hit && lang !== "cs");
}

function loadList() {
  var url = "/api/situations?q=" + encodeURIComponent(state.query) +
            "&audience=" + encodeURIComponent(state.audience);
  $("#list-count").textContent = t("loading");
  fetch(url).then(function (response) { return response.json(); })
    .then(function (data) {
      state.situations = data.situations || [];
      state.loaded = true;
      renderList();
    })
    .catch(function () { $("#list-count").textContent = t("error"); });
}

/* ---------------- obrazovka 2 ---------------- */

function deadlineBlock(step) {
  var box = el("div", "deadline");
  box.appendChild(el("div", "deadline-label", t("deadlineLabel")));

  if (step.deadline_status === "verified") {
    box.appendChild(el("div", "deadline-value", step.deadline_text || ""));
    if (step.deadline_source) {
      box.appendChild(el("div", "deadline-source", t("source") + step.deadline_source));
    }
  } else if (step.deadline_status === "not_applicable") {
    box.className = "deadline is-na";
    box.appendChild(el("div", "deadline-value", t("deadlineNA")));
  } else {
    box.className = "deadline is-todo";
    box.appendChild(el("div", "deadline-value", t("deadlineTodo")));
    if (step.verify_hint) {
      box.appendChild(el("div", "deadline-source", t("verifyHint") + step.verify_hint));
    }
  }
  return box;
}

function row(label, value) {
  var wrapper = el("div");
  wrapper.appendChild(el("div", "row-label", label));
  wrapper.appendChild(el("div", "row-value", value));
  return wrapper;
}

function documentsRow(documents) {
  var wrapper = el("div");
  wrapper.appendChild(el("div", "row-label", t("documents")));
  var value = el("div", "row-value");
  var list = el("ul");
  for (var i = 0; i < documents.length; i++) {
    list.appendChild(el("li", null, documents[i]));
  }
  value.appendChild(list);
  wrapper.appendChild(value);
  return wrapper;
}

function renderStep(step, index, fallback) {
  var item = el("li", "step" + (step.deadline_status === "manual_todo" ? " is-todo" : ""));

  var head = el("div", "step-head");
  head.appendChild(el("span", "step-number", String(index + 1)));
  head.appendChild(el("h3", null, field(step, "title", fallback)));
  item.appendChild(head);

  var body = field(step, "body", fallback);
  if (body) { item.appendChild(el("p", "step-body", body)); }

  item.appendChild(deadlineBlock(step));

  var rows = el("div", "rows");
  if (step.authority) { rows.appendChild(row(t("authority"), step.authority)); }
  if (step.location) { rows.appendChild(row(t("where"), step.location)); }
  if (step.office_hours) { rows.appendChild(row(t("hours"), step.office_hours)); }
  if (step.documents && step.documents.length) { rows.appendChild(documentsRow(step.documents)); }

  var sanction = el("div", "row-sanction");
  sanction.appendChild(el("div", "row-label", t("sanction")));
  sanction.appendChild(el("div", "row-value",
    step.sanction_text ? step.sanction_text : t("sanctionUnknown")));
  if (step.sanction_text && step.sanction_source) {
    sanction.appendChild(el("div", "deadline-source", t("source") + step.sanction_source));
  }
  rows.appendChild(sanction);
  item.appendChild(rows);

  var source = el("div", "step-source");
  if (step.source_url) {
    source.appendChild(document.createTextNode(t("sourceLink") + " (" + step.source_type + "): "));
    var link = el("a", null, step.source_url);
    link.href = step.source_url;
    link.rel = "noopener noreferrer";
    link.target = "_blank";
    source.appendChild(link);
  } else {
    source.textContent = t("noSourceUrl");
  }
  item.appendChild(source);
  return item;
}

/* Data ze stazene stranky praha13.cz. Bod 13 (lhuty) se zobrazuje zamerne
   jen jako surovy text k overeni - do kroku se nikdy neprepisuje. */
function renderPraha13Box(page) {
  var box = $("#p13-box");
  var list = $("#p13-list");
  list.innerHTML = "";
  $("#p13-source").textContent = "";
  if (!page) { box.hidden = true; return; }
  box.hidden = false;

  var pairs = [
    [t("p13Dept"), page.department],
    [t("p13Address"), page.address],
    [t("p13Hours"), page.office_hours],
    [t("p13Responsible"), page.responsible_department],
    [t("p13RawDeadline"), page.deadline_text_raw]
  ];
  for (var i = 0; i < pairs.length; i++) {
    if (!pairs[i][1]) { continue; }
    list.appendChild(el("dt", null, pairs[i][0]));
    list.appendChild(el("dd", null, pairs[i][1]));
  }
  var source = $("#p13-source");
  source.textContent = (page.fetched_at ? t("p13Fetched") + page.fetched_at + " — " : "");
  var link = el("a", null, page.url);
  link.href = page.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  source.appendChild(link);
}

function renderDetail(data) {
  var fallback = { hit: false };
  $("#detail-category").textContent = data.category || "";
  $("#detail-title").textContent = field(data, "title", fallback);
  $("#detail-summary").textContent = field(data, "summary", fallback);
  $("#detail-legend").textContent = t("legend");

  var list = $("#steps");
  list.innerHTML = "";
  for (var i = 0; i < data.steps.length; i++) {
    list.appendChild(renderStep(data.steps[i], i, fallback));
  }

  renderPraha13Box(data.praha13_page);

  var box = $("#katalog-box");
  var katalogList = $("#katalog-list");
  katalogList.innerHTML = "";
  var matches = data.katalog_matches || [];
  box.hidden = matches.length === 0;
  for (var j = 0; j < matches.length; j++) {
    var service = matches[j];
    var entry = el("li");
    entry.appendChild(document.createTextNode(service.name || service.id));
    var detail = [];
    if (service.agenda_name) { detail.push(service.agenda_name); }
    if (service.ohlasovatel_name) { detail.push(service.ohlasovatel_name); }
    if (detail.length) { entry.appendChild(el("span", "muted", " — " + detail.join(", "))); }
    katalogList.appendChild(entry);
  }

  var note = $("#detail-note");
  note.textContent = t("fallback");
  note.hidden = !(fallback.hit && lang !== "cs");
  window.scrollTo(0, 0);
}

function loadDetail(slug) {
  $("#detail-title").textContent = t("loading");
  $("#steps").innerHTML = "";
  fetch("/api/situations/" + encodeURIComponent(slug))
    .then(function (response) {
      if (!response.ok) { throw new Error("404"); }
      return response.json();
    })
    .then(renderDetail)
    .catch(function () { $("#detail-title").textContent = t("notFound"); });
}

/* ---------------- routovani ---------------- */

function route() {
  var hash = window.location.hash || "#/";
  var match = hash.match(/^#\/situace\/([^/?]+)/);
  if (match) {
    $("#screen-list").hidden = true;
    $("#screen-detail").hidden = false;
    loadDetail(decodeURIComponent(match[1]));
  } else {
    $("#screen-detail").hidden = true;
    $("#screen-list").hidden = false;
    if (!state.loaded) { loadList(); } else { renderList(); }
  }
}

function setLang(next) {
  if (LANGS.indexOf(next) === -1) { return; }
  lang = next;
  applyStaticTexts();
  route();
}

function init() {
  applyStaticTexts();

  var buttons = document.querySelectorAll(".lang-btn");
  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener("click", function (event) {
      setLang(event.currentTarget.dataset.lang);
    });
  }

  var chips = document.querySelectorAll(".chip");
  for (var j = 0; j < chips.length; j++) {
    chips[j].addEventListener("click", function (event) {
      var all = document.querySelectorAll(".chip");
      for (var k = 0; k < all.length; k++) { all[k].classList.remove("is-active"); }
      event.currentTarget.classList.add("is-active");
      state.audience = event.currentTarget.dataset.audience || "";
      loadList();
    });
  }

  var timer = null;
  $("#search").addEventListener("input", function (event) {
    state.query = event.target.value;
    window.clearTimeout(timer);
    timer = window.setTimeout(loadList, 180);
  });

  window.addEventListener("hashchange", route);

  fetch("/api/stats").then(function (r) { return r.json(); }).then(function (data) {
    $("#footer-stats").textContent =
      "Situací: " + data.situations + " | kroků: " + data.steps +
      " | ověřených lhůt: " + data.steps_verified +
      " | lhůt k ověření: " + data.steps_manual_todo +
      " | záznamů z Katalogu služeb: " + data.katalog_services +
      " | stažených stránek praha13.cz: " + data.praha13_pages;
  }).catch(function () { /* statistika je jen doplnek */ });

  route();
}

init();
