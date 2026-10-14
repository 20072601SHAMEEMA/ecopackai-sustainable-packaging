/*
 * EcoPackAI - Shared layout components
 * Module: Frontend UI
 *
 * Reusable header (navigation bar) and footer, defined once and inserted into
 * every page's <header id="site-header"> and <footer id="site-footer">.
 * The current page's link is highlighted. Pages stay usable without this file
 * (each page has its own <noscript> links).
 */
(function () {
  "use strict";

  const PAGES = [
    { href: "index.html", label: "Home" },
    { href: "predict.html", label: "Get Recommendation" },
    { href: "results.html", label: "Results" },
    { href: "dashboard.html", label: "Analytics" },
  ];

  function currentPage() {
    const name = window.location.pathname.split("/").pop();
    return name === "" ? "index.html" : name;
  }

  function buildHeader() {
    const nav = document.createElement("nav");
    nav.className = "navbar navbar-expand-md navbar-dark bg-eco";
    nav.setAttribute("aria-label", "Main navigation");

    const container = document.createElement("div");
    container.className = "container";

    const brand = document.createElement("a");
    brand.className = "navbar-brand fw-semibold";
    brand.href = "index.html";
    brand.textContent = "EcoPackAI";

    const toggler = document.createElement("button");
    toggler.className = "navbar-toggler";
    toggler.type = "button";
    toggler.setAttribute("data-bs-toggle", "collapse");
    toggler.setAttribute("data-bs-target", "#main-nav");
    toggler.setAttribute("aria-controls", "main-nav");
    toggler.setAttribute("aria-expanded", "false");
    toggler.setAttribute("aria-label", "Toggle navigation");
    const icon = document.createElement("span");
    icon.className = "navbar-toggler-icon";
    toggler.appendChild(icon);

    const collapse = document.createElement("div");
    collapse.className = "collapse navbar-collapse";
    collapse.id = "main-nav";
    const list = document.createElement("ul");
    list.className = "navbar-nav ms-auto";
    PAGES.forEach(function (page) {
      const item = document.createElement("li");
      item.className = "nav-item";
      const link = document.createElement("a");
      link.className = "nav-link";
      link.href = page.href;
      link.textContent = page.label;
      if (page.href === currentPage()) {
        link.classList.add("active");
        link.setAttribute("aria-current", "page");
      }
      item.appendChild(link);
      list.appendChild(item);
    });
    collapse.appendChild(list);

    container.append(brand, toggler, collapse);
    nav.appendChild(container);
    return nav;
  }

  function buildFooter() {
    const wrapper = document.createElement("div");
    wrapper.className = "container py-3 small text-body-secondary d-flex flex-wrap justify-content-between gap-2";
    const left = document.createElement("span");
    left.textContent = "EcoPackAI — AI-powered sustainable packaging recommendations";
    const right = document.createElement("span");
    right.textContent = "Models: Random Forest (cost) · XGBoost (CO₂)";
    wrapper.append(left, right);
    return wrapper;
  }

  function init() {
    const header = document.getElementById("site-header");
    const footer = document.getElementById("site-footer");
    if (header) header.replaceChildren(buildHeader());
    if (footer) footer.replaceChildren(buildFooter());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
}());
