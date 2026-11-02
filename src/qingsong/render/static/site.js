(function () {
  "use strict";
  var prefix = window.QINGSONG_PREFIX || "";

  // Language switch, remembered per viewer when the browser allows it.
  function show(mode) {
    document.body.classList.remove("show-en", "show-zh", "show-both");
    document.body.classList.add("show-" + mode);
    document.querySelectorAll(".language-switch button").forEach(function (button) {
      button.classList.toggle("active", button.dataset.show === mode);
    });
    try { localStorage.setItem("qingsong-language", mode); } catch (error) { /* storage unavailable */ }
  }
  var saved = null;
  try { saved = localStorage.getItem("qingsong-language"); } catch (error) { saved = null; }
  show(saved === "en" || saved === "zh" ? saved : "both");
  document.querySelectorAll(".language-switch button").forEach(function (button) {
    button.addEventListener("click", function () { show(button.dataset.show); });
  });

  // Review marks (labels and proposed fixes) in documents, shown unless the viewer hides them.
  var marks = document.getElementById("marks-switch");
  function showMarks(on) {
    document.body.classList.toggle("hide-marks", !on);
    if (marks) { marks.textContent = on ? "Marks on" : "Marks off"; marks.classList.toggle("active", on); }
    try { localStorage.setItem("qingsong-marks", on ? "on" : "off"); } catch (error) { /* storage unavailable */ }
  }
  var savedMarks = null;
  try { savedMarks = localStorage.getItem("qingsong-marks"); } catch (error) { savedMarks = null; }
  showMarks(savedMarks !== "off");
  if (marks) { marks.addEventListener("click", function () { showMarks(document.body.classList.contains("hide-marks")); }); }

  // Search over IDs, aliases, titles and texts (both languages).
  var input = document.getElementById("search");
  var results = document.getElementById("search-results");
  var index = window.QINGSONG_INDEX || [];
  if (!input || !results) { return; }
  function escape(text) {
    return String(text).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;"}[c]; });
  }
  input.addEventListener("input", function () {
    var query = input.value.trim().toLowerCase();
    if (query.length < 2) { results.style.display = "none"; return; }
    var hits = [];
    index.forEach(function (entry) {
      var haystack = [entry.id, entry.title, entry.title_zh, entry.aliases.join(" "), entry.text].join(" ").toLowerCase();
      var position = haystack.indexOf(query);
      if (position >= 0) {
        var score = entry.id.toLowerCase().indexOf(query) >= 0 ? 0 : (entry.aliases.join(" ").toLowerCase().indexOf(query) >= 0 ? 1 : 2);
        hits.push({entry: entry, score: score});
      }
    });
    hits.sort(function (a, b) { return a.score - b.score || a.entry.id.localeCompare(b.entry.id); });
    results.innerHTML = hits.slice(0, 30).map(function (hit) {
      var entry = hit.entry;
      var alias = entry.aliases.length ? " <span class=\"type\">(" + escape(entry.aliases.join(", ")) + ")</span>" : "";
      return "<a href=\"" + prefix + escape(entry.url) + "\"><b>" + escape(entry.id) + "</b>" + alias + " <span class=\"type\">" + escape(entry.type) + "</span><br>" +
        escape(entry.title) + (entry.title_zh ? " · " + escape(entry.title_zh) : "") + "</a>";
    }).join("") || "<a>No match</a>";
    results.style.display = "block";
  });
  document.addEventListener("click", function (event) {
    if (!results.contains(event.target) && event.target !== input) { results.style.display = "none"; }
  });
})();
