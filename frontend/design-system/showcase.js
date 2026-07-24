/* UI-01 showcase interactivity — vanilla JS, no build step, no dependencies.
   Also demonstrates the analytics event taxonomy: every meaningful interaction
   calls track(), which logs to the console (a real analytics sink is a future
   cycle — see docs/design/ANALYTICS_EVENTS.md). All data here is MOCK. */

const analyticsLog = [];
function track(event, props = {}) {
  const entry = { event, props, ts: new Date().toISOString() };
  analyticsLog.push(entry);
  // eslint-disable-next-line no-console
  console.info("[analytics]", event, props);
  const el = document.getElementById("analytics-feed");
  if (el) {
    const li = document.createElement("li");
    li.className = "small";
    li.textContent = `${entry.ts.slice(11, 19)}  ${event}  ${JSON.stringify(props)}`;
    el.prepend(li);
  }
}

/* Theme toggle */
function initTheme() {
  const btn = document.getElementById("theme-toggle");
  btn?.addEventListener("click", () => {
    const root = document.documentElement;
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    btn.setAttribute("aria-pressed", String(next === "dark"));
    btn.textContent = next === "dark" ? "☀️ Light" : "🌙 Dark";
  });
}

/* Accessible tabs (roving, aria-selected) */
function initTabs() {
  document.querySelectorAll("[role=tablist]").forEach((list) => {
    const tabs = [...list.querySelectorAll("[role=tab]")];
    const select = (tab) => {
      tabs.forEach((t) => {
        const on = t === tab;
        t.setAttribute("aria-selected", String(on));
        t.tabIndex = on ? 0 : -1;
        document.getElementById(t.getAttribute("aria-controls"))?.toggleAttribute("hidden", !on);
      });
      track("tab_switched", { tab: tab.textContent.trim() });
    };
    tabs.forEach((tab, i) => {
      tab.addEventListener("click", () => select(tab));
      tab.addEventListener("keydown", (e) => {
        if (e.key === "ArrowRight") { select(tabs[(i + 1) % tabs.length]); tabs[(i + 1) % tabs.length].focus(); }
        if (e.key === "ArrowLeft") { select(tabs[(i - 1 + tabs.length) % tabs.length]); tabs[(i - 1 + tabs.length) % tabs.length].focus(); }
      });
    });
  });
}

/* Modal with focus trap + Escape */
function initModal() {
  const overlay = document.getElementById("modal-overlay");
  const open = document.getElementById("open-modal");
  const close = document.getElementById("close-modal");
  let lastFocus = null;
  const show = () => { lastFocus = document.activeElement; overlay.hidden = false; close.focus(); track("modal_opened", { id: "cancellation-policy" }); };
  const hide = () => { overlay.hidden = true; lastFocus?.focus(); };
  open?.addEventListener("click", show);
  close?.addEventListener("click", hide);
  overlay?.addEventListener("click", (e) => { if (e.target === overlay) hide(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !overlay.hidden) hide(); });
}

/* Favourites */
function initFavourites() {
  document.querySelectorAll(".card__fav").forEach((btn) => {
    btn.addEventListener("click", () => {
      const on = btn.getAttribute("aria-pressed") === "true";
      btn.setAttribute("aria-pressed", String(!on));
      btn.textContent = on ? "♡" : "♥";
      track(on ? "favorite_removed" : "favorite_added", { listing_id: btn.dataset.listing });
    });
  });
}

/* Search + filters (mock) */
function initSearch() {
  const form = document.getElementById("search-form");
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    track("search_started", { city: data.city, guests: data.guests });
    const results = document.getElementById("search-results");
    if (results) {
      results.textContent = `Mock: showing stays in ${data.city || "anywhere"} for ${data.guests || 1} guest(s), €${data.price_min || 0}–€${data.price_max || 500}/night.`;
      track("search_completed", { results: 24 });
    }
  });
  document.querySelectorAll("[data-filter]").forEach((chip) => {
    chip.addEventListener("click", () => {
      const on = chip.getAttribute("aria-pressed") === "true";
      chip.setAttribute("aria-pressed", String(!on));
      track("filter_applied", { filter: chip.dataset.filter, on: !on });
    });
  });
}

/* Booking CTA (mock) */
function initBooking() {
  document.querySelectorAll("[data-book]").forEach((btn) => {
    btn.addEventListener("click", () => {
      track("booking_started", { listing_id: btn.dataset.book });
      track("payment_started", { method: "card" });
      const status = document.getElementById("booking-status");
      if (status) status.hidden = false;
    });
  });
}

/* Mobile: bottom nav, map/list toggle, bottom sheet */
function initMobile() {
  const nav = document.querySelector(".m-bottomnav");
  nav?.querySelectorAll("button").forEach((b) => {
    b.addEventListener("click", () => {
      nav.querySelectorAll("button").forEach((x) => x.removeAttribute("aria-current"));
      b.setAttribute("aria-current", "page");
      document.querySelectorAll(".device__screen").forEach((s) => s.toggleAttribute("hidden", s.dataset.screen !== b.dataset.target));
      track("mobile_tab", { tab: b.dataset.target });
    });
  });
  document.querySelectorAll(".seg button").forEach((b) => {
    b.addEventListener("click", () => {
      b.parentElement.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", "false"));
      b.setAttribute("aria-pressed", "true");
      track("map_list_toggle", { view: b.dataset.view });
    });
  });
  const sheet = document.getElementById("m-sheet");
  const sheetOverlay = document.getElementById("m-sheet-overlay");
  document.getElementById("m-open-sheet")?.addEventListener("click", () => { sheet.hidden = false; sheetOverlay.hidden = false; track("filter_sheet_opened"); });
  const closeSheet = () => { sheet.hidden = true; sheetOverlay.hidden = true; };
  sheetOverlay?.addEventListener("click", closeSheet);
  document.getElementById("m-apply-sheet")?.addEventListener("click", () => { closeSheet(); track("filter_applied", { source: "mobile_sheet" }); });
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme(); initTabs(); initModal(); initFavourites();
  initSearch(); initBooking(); initMobile();
  track("showcase_loaded", {});
});
