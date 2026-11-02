(function () {
  "use strict";
  // Review page: filters, and decisions kept in this browser until saved as a decisions file
  // (docs/SPEC.md §5.6).
  var project = document.body.dataset.project || "";
  var decisionKey = "qingsong-review-decisions:" + project;
  var reviewerKey = "qingsong-reviewer:" + project;

  function read(key, fallback) {
    try { var value = localStorage.getItem(key); return value === null ? fallback : value; } catch (error) { return fallback; }
  }
  function write(key, value) {
    try { localStorage.setItem(key, value); } catch (error) { /* storage unavailable: marks last for this visit */ }
  }
  var decisions = {};
  try { decisions = JSON.parse(read(decisionKey, "{}")) || {}; } catch (error) { decisions = {}; }
  function saveDecisions() { write(decisionKey, JSON.stringify(decisions)); }
  // Keep only marks for proposals that are still open on this page and read as they are now: a
  // mark made on a proposal that has changed since is dropped, so it is read again.
  var open_hashes = {};
  document.querySelectorAll(".issue-card .proposal[data-key]").forEach(function (box) {
    if (box.querySelector("button[data-decision]")) { open_hashes[box.dataset.key] = box.dataset.hash || ""; }
  });
  var dropped = [];
  Object.keys(decisions).forEach(function (key) {
    if (!(key in open_hashes)) { delete decisions[key]; return; }
    if (decisions[key].hash !== open_hashes[key]) { delete decisions[key]; dropped.push(key.replace("#", " proposal ")); }
  });
  saveDecisions();

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
          decisions[key] = {decision: button.dataset.decision, note: note ? note.value : "", hash: box.dataset.hash || ""};
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
    var remembered = read(reviewerKey, "") || reviewer.getAttribute("data-default") || "";
    var known = Array.prototype.some.call(reviewer.options, function (option) { return option.value === remembered; });
    reviewer.value = known ? remembered : "";
    reviewer.addEventListener("change", function () { write(reviewerKey, reviewer.value); });
  }
  function by_issue_and_number(first, second) {
    var a = first.split("#"), b = second.split("#");
    return a[0] === b[0] ? Number(a[1]) - Number(b[1]) : (a[0] < b[0] ? -1 : 1);
  }
  // A JSON string is also a YAML double-quoted string, so notes need no further escaping.
  function yaml_string(text) { return JSON.stringify(String(text)); }
  function two_digits(number) { return (number < 10 ? "0" : "") + number; }
  function local_date(moment) {
    return moment.getFullYear() + "-" + two_digits(moment.getMonth() + 1) + "-" + two_digits(moment.getDate());
  }
  function decisions_text() {
    var lines = [
      "# Review decisions. Apply them with: qingsong issue apply FILE",
      "format: qingsong-decisions/1",
      "project: " + yaml_string(project),
      "decided_by: " + yaml_string(reviewer ? reviewer.value : ""),
      "saved: " + yaml_string(new Date().toISOString()),
      "decisions:"
    ];
    Object.keys(decisions).sort(by_issue_and_number).forEach(function (key) {
      var parts = key.split("#"), decision = decisions[key];
      lines.push("  - issue: " + yaml_string(parts[0]));
      lines.push("    proposal: " + Number(parts[1]));
      lines.push("    decision: " + (decision.decision === "accept" ? "accept" : "reject"));
      if (decision.note && decision.note.trim()) { lines.push("    note: " + yaml_string(decision.note.trim())); }
      lines.push("    proposal_hash: " + yaml_string(decision.hash || ""));
    });
    return lines.join("\n") + "\n";
  }
  var output = document.getElementById("decision-output");
  function show(text) {
    if (!output) { return; }
    output.hidden = false;
    output.value = text;
  }
  if (dropped.length) {
    show("# These marks were dropped because the proposal changed since you marked it; read it again:\n# " + dropped.join(", "));
  }
  function ready() {
    if (reviewer && !reviewer.value) {
      show("# Choose your name under \"You are\" first: the file records who decided.");
      reviewer.focus();
      return false;
    }
    if (!Object.keys(decisions).length) {
      show("# No proposal is marked yet.");
      return false;
    }
    return true;
  }
  function flash(button, text, label) {
    button.textContent = text;
    setTimeout(function () { button.textContent = label; }, 2500);
  }
  var save = document.getElementById("save-decisions");
  if (save) {
    save.addEventListener("click", function () {
      if (!ready()) { return; }
      var text = decisions_text();
      show(text);
      var link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob([text], {type: "text/yaml;charset=utf-8"}));
      link.download = "decisions_" + (project || "review") + "_" + local_date(new Date()) + "_" + (reviewer ? reviewer.value : "") + ".yaml";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(function () { URL.revokeObjectURL(link.href); }, 2000);
      flash(save, "Saved", "Save decisions");
    });
  }
  var copy = document.getElementById("copy-decisions");
  if (copy) {
    copy.addEventListener("click", function () {
      if (!ready()) { return; }
      var text = decisions_text();
      show(text);
      if (output) { output.focus(); output.select(); }
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(
          function () { flash(copy, "Copied", "Copy decisions"); },
          function () { flash(copy, "Select and copy", "Copy decisions"); });
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
