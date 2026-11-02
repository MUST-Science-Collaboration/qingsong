(function () {
  "use strict";
  // Review page: filters, and decisions kept in this browser until copied as commands.
  var decisionKey = "qingsong-review-decisions";
  var reviewerKey = "qingsong-reviewer";

  function read(key, fallback) {
    try { var value = localStorage.getItem(key); return value === null ? fallback : value; } catch (error) { return fallback; }
  }
  function write(key, value) {
    try { localStorage.setItem(key, value); } catch (error) { /* storage unavailable: marks last for this visit */ }
  }
  var decisions = {};
  try { decisions = JSON.parse(read(decisionKey, "{}")) || {}; } catch (error) { decisions = {}; }
  function saveDecisions() { write(decisionKey, JSON.stringify(decisions)); }

  // Filters ------------------------------------------------------------------------------------
  var active = {kind: "", state: "", document: ""};
  var cards = Array.prototype.slice.call(document.querySelectorAll(".issue-card"));
  var empty = document.getElementById("filter-empty");
  function applyFilters() {
    var shown = 0;
    cards.forEach(function (card) {
      var documents = " " + (card.dataset.documents || "") + " ";
      var visible = (!active.kind || card.dataset.kind === active.kind) &&
        (!active.state || card.dataset.state === active.state) &&
        (!active.document || documents.indexOf(" " + active.document + " ") >= 0);
      card.hidden = !visible;
      if (visible) { shown += 1; }
    });
    if (empty) { empty.hidden = shown > 0; }
    document.querySelectorAll("[data-filter]").forEach(function (control) {
      if (control.tagName === "SELECT") { control.value = active[control.dataset.filter]; return; }
      control.classList.toggle("active", active[control.dataset.filter] === control.dataset.value);
    });
  }
  document.querySelectorAll("button[data-filter]").forEach(function (button) {
    button.addEventListener("click", function () {
      var name = button.dataset.filter;
      active[name] = (active[name] === button.dataset.value && button.classList.contains("tile")) ? "" : button.dataset.value;
      applyFilters();
    });
  });
  document.querySelectorAll("select[data-filter]").forEach(function (select) {
    select.addEventListener("change", function () { active[select.dataset.filter] = select.value; applyFilters(); });
  });
  if (location.hash) {
    var target = document.getElementById(location.hash.slice(1));
    if (target && target.classList.contains("issue-card")) { target.classList.add("focus"); }
  }

  // Decisions ----------------------------------------------------------------------------------
  var counter = document.getElementById("decision-count");
  function showCount() {
    var count = Object.keys(decisions).length;
    if (counter) { counter.textContent = count + (count === 1 ? " proposal marked" : " proposals marked"); }
  }
  document.querySelectorAll(".issue-card .proposal[data-key]").forEach(function (box) {
    var key = box.dataset.key;
    var buttons = box.querySelectorAll("button[data-decision]");
    var note = box.querySelector(".decision-note");
    function paint() {
      var decision = decisions[key];
      buttons.forEach(function (button) {
        button.classList.toggle("chosen", !!decision && decision.decision === button.dataset.decision);
      });
      box.classList.toggle("decided", !!decision);
      if (note && decision && typeof decision.note === "string" && note.value !== decision.note) { note.value = decision.note; }
    }
    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        var current = decisions[key];
        if (current && current.decision === button.dataset.decision) {
          delete decisions[key];
        } else {
          decisions[key] = {decision: button.dataset.decision, note: note ? note.value : ""};
        }
        saveDecisions(); paint(); showCount();
      });
    });
    if (note) {
      note.addEventListener("input", function () {
        if (decisions[key]) { decisions[key].note = note.value; saveDecisions(); }
      });
    }
    paint();
  });
  showCount();

  var reviewer = document.getElementById("reviewer");
  if (reviewer) {
    reviewer.value = read(reviewerKey, "");
    reviewer.addEventListener("input", function () { write(reviewerKey, reviewer.value.trim()); });
  }
  function quote(text) { return "'" + String(text).replace(/'/g, "'\\''") + "'"; }
  function commands() {
    var person = (reviewer && reviewer.value.trim()) || "YOUR_ID";
    var lines = [];
    Object.keys(decisions).sort().forEach(function (key) {
      var parts = key.split("#"), decision = decisions[key];
      if (decision.decision === "accept") {
        if (decision.note) { lines.push("# " + parts[0] + " proposal " + parts[1] + ": " + decision.note.replace(/\n/g, " ")); }
        lines.push("qingsong issue accept " + parts[0] + " --proposal " + parts[1] + " --by " + person);
      } else {
        lines.push("qingsong issue reject " + parts[0] + " --proposal " + parts[1] + " --by " + person +
          " --reason " + quote(decision.note || "rejected in review"));
      }
    });
    return lines.join("\n");
  }
  var output = document.getElementById("decision-output");
  var copy = document.getElementById("copy-decisions");
  if (copy && output) {
    copy.addEventListener("click", function () {
      var text = commands();
      output.hidden = false;
      output.value = text || "# No proposal is marked yet.";
      output.focus(); output.select();
      if (text && navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function () { copy.textContent = "Copied"; }, function () { copy.textContent = "Select and copy"; });
        setTimeout(function () { copy.textContent = "Copy decisions"; }, 2500);
      }
    });
  }
  var clear = document.getElementById("clear-decisions");
  if (clear) {
    clear.addEventListener("click", function () {
      decisions = {}; saveDecisions();
      document.querySelectorAll(".proposal.decided").forEach(function (box) { box.classList.remove("decided"); });
      document.querySelectorAll("button.chosen").forEach(function (button) { button.classList.remove("chosen"); });
      document.querySelectorAll(".decision-note").forEach(function (note) { note.value = ""; });
      if (output) { output.hidden = true; }
      showCount();
    });
  }
})();
