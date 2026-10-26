/*
 * The demo page's one script (PRD 8.2): sends the ask box without leaving the page. The page works
 * without it, as a plain form the server answers with the whole page.
 *
 * While an answer is on its way, the status line says "Searching the help center…" and every
 * button that sends the box rests. The server sends back the ask box alone, which replaces this
 * one; then the newest turn, or the notice that refused it, takes the focus so it's read next. A
 * suggested question or a clarifying option sends the same form with its own value. Nothing is
 * stored in the browser.
 *
 * A citation marker opens its quote in place, under the answer, instead of jumping to it; without
 * the script the marker is a link, and the quote it lands on opens itself.
 */
(function () {
  "use strict";
  if (!window.fetch || !window.DOMParser) return;

  function rest(busy) {
    document.querySelectorAll('[form="ask-form"], #ask-form button').forEach(function (button) {
      button.disabled = busy;
    });
  }

  // The hour's limit rests the box for the minutes it names, then the box opens again by itself
  var reopening;
  function reopenAfterWait() {
    clearTimeout(reopening);
    var form = document.getElementById("ask-form");
    var minutes = form ? Number(form.getAttribute("data-wait")) : 0;
    if (minutes > 0) {
      reopening = setTimeout(function () {
        var status = document.querySelector("[data-status]");
        if (status) status.textContent = "";
        rest(false);
      }, minutes * 60000);
    }
  }
  reopenAfterWait();

  document.addEventListener("click", function (event) {
    var marker = event.target.closest(".cm-reply .cm-cite");
    if (!marker) return;
    var source = document.getElementById(marker.getAttribute("href").slice(1));
    if (!source) return;
    event.preventDefault();
    var reply = marker.closest(".cm-reply");
    var opening = !source.classList.contains("is-open");
    reply.querySelectorAll(".cm-source.is-open").forEach(function (open) {
      open.classList.remove("is-open");
    });
    reply.querySelectorAll(".cm-cite").forEach(function (other) {
      var on = opening && other.getAttribute("href") === marker.getAttribute("href");
      other.classList.toggle("is-active", on);
      other.setAttribute("aria-expanded", String(on));
    });
    if (opening) source.classList.add("is-open");
  });

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
        // The day's cap closes the box: the server sends Send disabled, and the suggestions rest with it
        var send = fresh.querySelector("#ask-form > .cm-btn-primary");
        rest(Boolean(send && send.disabled));
        reopenAfterWait();
        var notice = fresh.querySelector("[data-status]");
        var turns = fresh.querySelectorAll(".cm-asked > .cm-turn");
        if (notice.textContent) {
          notice.setAttribute("tabindex", "-1");
          notice.focus();
        } else if (turns.length) {
          turns[turns.length - 1].classList.add("is-new");
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
