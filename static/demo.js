/*
 * The demo page's one script (PRD 8.2): sends the ask box without leaving the page. The page works
 * without it, as a plain form the server answers with the whole page.
 *
 * While an answer is on its way, the status line says "Searching the help center…" and every
 * button that sends the box rests. The server sends back the ask box alone, which replaces this
 * one; then the newest turn, or the notice that refused it, takes the focus so it's read next. A
 * suggested question or a clarifying option sends the same form with its own value. Nothing is
 * stored in the browser.
 */
(function () {
  "use strict";
  if (!window.fetch || !window.DOMParser) return;

  function rest(busy) {
    document.querySelectorAll('[form="ask-form"], #ask-form button').forEach(function (button) {
      button.disabled = busy;
    });
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (form.id !== "ask-form") return;
    event.preventDefault();
    var box = form.closest("[data-ask-box]");
    if (box.getAttribute("aria-busy") === "true") return;
    var status = box.querySelector("[data-status]");
    var data = new URLSearchParams(new FormData(form));
    var submitter = event.submitter;
    if (submitter && submitter.name) data.set(submitter.name, submitter.value);
    status.textContent = form.getAttribute("data-searching");
    box.setAttribute("aria-busy", "true");
    rest(true);
    fetch(form.action, {
      method: "POST",
      body: data,
      headers: { "X-Citemark-Fragment": "ask" },
      credentials: "same-origin",
    })
      .then(function (response) {
        // A refusal (the hour's limit, the day's cap) or a failed answer still comes as the box
        if (!response.ok && [429, 502, 503].indexOf(response.status) === -1) throw new Error(String(response.status));
        return response.text();
      })
      .then(function (html) {
        var fresh = new DOMParser().parseFromString(html, "text/html").querySelector("[data-ask-box]");
        if (!fresh) throw new Error("no ask box");
        box.replaceWith(fresh);
        rest(false);
        var notice = fresh.querySelector("[data-status]");
        var turns = fresh.querySelectorAll(".cm-asked > .cm-turn");
        if (notice.textContent) {
          notice.setAttribute("tabindex", "-1");
          notice.focus();
        } else if (turns.length) {
          turns[turns.length - 1].focus();
        }
      })
      .catch(function () {
        status.textContent = form.getAttribute("data-failed");
        box.setAttribute("aria-busy", "false");
        rest(false);
      });
  });
})();
