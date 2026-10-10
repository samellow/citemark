/*
 * The report's one script (PRD 8.1): a filter over the question list, and everything unfolded for
 * print. The report reads in full without it: the filter stays hidden, and the folded passes open
 * with their own disclosure.
 *
 * A count in the measures links to #show-<measure>, which filters the list to the questions that
 * failed that measure, on every click. A link to a question the filter hides, such as one from the
 * fix plan, shows every question again, unfolding the passes if it's among them.
 */
(function () {
  "use strict";
  var bar = document.querySelector("[data-filter]");
  var list = document.querySelector("[data-questions]");
  var passes = list && list.querySelector(".cm-passes");

  function show(what) {
    if (!bar.querySelector('[data-show="' + what + '"]')) return false;
    bar.querySelectorAll("[data-show]").forEach(function (button) {
      button.setAttribute("aria-pressed", String(button.getAttribute("data-show") === what));
    });
    list.querySelectorAll("[data-entry]").forEach(function (entry) {
      var failed = entry.getAttribute("data-state") === "fail";
      var measures = " " + entry.getAttribute("data-failed") + " ";
      var kept = what === "all" || (what === "failed" ? failed : measures.indexOf(" " + what + " ") !== -1);
      entry.hidden = !kept;
    });
    if (passes) passes.hidden = what !== "all";
    return true;
  }

  function filtered(hash) {
    var wanted = /^#show-(\w+)$/.exec(hash);
    if (wanted && show(wanted[1])) {
      list.scrollIntoView();
      return true;
    }
    return false;
  }

  function reveal(hash) {
    var target = hash && document.getElementById(hash.slice(1));
    if (!target || !list.contains(target)) return;
    var entry = target.closest("[data-entry]");
    var folded = passes && passes.contains(target) && (!passes.open || passes.hidden);
    if ((entry && entry.hidden) || folded) {
      show("all");
      if (passes && passes.contains(target)) passes.open = true;
      target.scrollIntoView();
    }
  }

  if (bar && list) {
    bar.hidden = false;
    bar.addEventListener("click", function (event) {
      var button = event.target.closest("[data-show]");
      if (button) show(button.getAttribute("data-show"));
    });
    document.addEventListener("click", function (event) {
      var link = event.target.closest('a[href^="#"]');
      if (!link) return;
      var hash = link.getAttribute("href");
      if (/^#show-/.test(hash)) {
        filtered(hash); // even when the address already holds it, so no hashchange follows
      } else {
        reveal(hash); // before the browser scrolls, so the target is visible to scroll to
      }
    });
    window.addEventListener("hashchange", function () {
      if (!filtered(window.location.hash)) reveal(window.location.hash);
    });
    if (!filtered(window.location.hash)) reveal(window.location.hash);
  }

  var opened = [];
  window.addEventListener("beforeprint", function () {
    if (bar && list) show("all");
    document.querySelectorAll("details:not([open])").forEach(function (details) {
      details.open = true;
      opened.push(details);
    });
  });
  window.addEventListener("afterprint", function () {
    opened.forEach(function (details) { details.open = false; });
    opened = [];
  });
})();
