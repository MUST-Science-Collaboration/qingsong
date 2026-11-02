(function () {
  "use strict";
  var data = window.QINGSONG_TREE;
  var canvas = document.getElementById("tree-canvas");
  var panel = document.getElementById("tree-panel");
  if (!data || !canvas) { return; }
  var svgNS = "http://www.w3.org/2000/svg";
  var recordBase = window.QINGSONG_RECORD_BASE || "";
  var columnWidth = 250, boxWidth = 220, boxHeight = 42, rowHeight = 52, margin = 16;
  var colors = {
    product: {stroke: "#c2410c", fill: "#fff7ed"},
    work: {stroke: "#9ca3af", fill: "#ffffff"},
    context: {stroke: "#1d4ed8", fill: "#eff6ff"}
  };
  var collapsed = {};
  var selected = null;
  var byReference = {};

  function index(node, depth, parent) {
    node.depth = depth;
    node.parent = parent;
    byReference[node.reference] = node;
    if (depth >= 2 && node.children.length) { collapsed[node.reference] = true; }
    node.children.forEach(function (child) { index(child, depth + 1, node); });
  }
  index(data, 0, null);

  function width(text) {
    var count = 0;
    for (var i = 0; i < text.length; i++) { count += text.charCodeAt(i) > 0x2e80 ? 2 : 1.05; }
    return count;
  }
  function fit(text, limit) {
    if (width(text) <= limit) { return text; }
    var out = "";
    for (var i = 0; i < text.length; i++) {
      if (width(out + text[i]) > limit - 1) { return out + "…"; }
      out += text[i];
    }
    return out;
  }
  function element(name, attributes, parent) {
    var node = document.createElementNS(svgNS, name);
    Object.keys(attributes).forEach(function (key) { node.setAttribute(key, attributes[key]); });
    if (parent) { parent.appendChild(node); }
    return node;
  }

  function layout(node, state) {
    var visible = collapsed[node.reference] ? [] : node.children;
    node.x = margin + node.depth * columnWidth;
    if (!visible.length) {
      node.y = margin + state.row * rowHeight;
      state.row += 1;
    } else {
      visible.forEach(function (child) { layout(child, state); });
      node.y = (visible[0].y + visible[visible.length - 1].y) / 2;
    }
    state.depth = Math.max(state.depth, node.depth);
    return state;
  }

  function draw() {
    var state = layout(data, {row: 0, depth: 0});
    canvas.innerHTML = "";
    var svg = element("svg", {
      width: margin * 2 + (state.depth + 1) * columnWidth,
      height: margin * 2 + state.row * rowHeight,
      role: "img", "aria-label": "Product tree"
    }, canvas);
    var edges = element("g", {}, svg);
    var nodes = element("g", {}, svg);
    (function visit(node) {
      var visible = collapsed[node.reference] ? [] : node.children;
      visible.forEach(function (child) {
        var x1 = node.x + boxWidth, y1 = node.y + boxHeight / 2, x2 = child.x, y2 = child.y + boxHeight / 2;
        var middle = (x1 + x2) / 2;
        element("path", {d: "M" + x1 + "," + y1 + " C" + middle + "," + y1 + " " + middle + "," + y2 + " " + x2 + "," + y2,
                         fill: "none", stroke: "#d1d5db", "stroke-width": 1.5}, edges);
        visit(child);
      });
      drawNode(node, nodes);
    })(data);
  }

  function drawNode(node, parent) {
    var color = colors[node.kind] || colors.product;
    var group = element("g", {"class": "tnode" + (selected === node ? " selected" : ""), transform: "translate(" + node.x + "," + node.y + ")",
                              tabindex: 0, role: "button", "aria-label": node.reference}, parent);
    var dashed = node.kind === "work" || node.status === "placeholder";
    element("rect", {width: boxWidth, height: boxHeight, rx: 6, fill: color.fill,
                     stroke: node.status === "placeholder" ? "#f59e0b" : color.stroke,
                     "stroke-dasharray": dashed ? "5 3" : "none"}, group);
    var title = element("text", {x: 9, y: 17, "font-size": 13, "font-weight": "bold", fill: "#1f2937"}, group);
    title.textContent = node.code;
    if (node.structural_code) {
      var code = element("text", {x: 0, y: 17, "font-size": 11, fill: "#6b7280"}, group);
      code.textContent = node.structural_code;
      var measured = 0;
      try { measured = title.getComputedTextLength(); } catch (error) { measured = 0; }
      code.setAttribute("x", 9 + (measured || width(node.code) * 9.5) + 6);
    }
    var name = element("text", {x: 9, y: 33, "font-size": 11.5, fill: "#374151"}, group);
    name.textContent = fit(node.names.en + (node.names.zh ? " " + node.names.zh : ""), 34);
    if (node.total) {
      element("circle", {cx: boxWidth - 16, cy: 13, r: 10, fill: "#c2410c"}, group);
      var count = element("text", {x: boxWidth - 16, y: 17, "font-size": 10.5, fill: "#fff", "text-anchor": "middle"}, group);
      count.textContent = node.total;
    }
    if (node.children.length) {
      var marker = element("text", {x: boxWidth - 16, y: 36, "font-size": 12, fill: "#6b7280", "text-anchor": "middle"}, group);
      marker.textContent = collapsed[node.reference] ? "▸ " + node.children.length : "▾";
    }
    function activate() {
      if (node.children.length) { collapsed[node.reference] = !collapsed[node.reference]; }
      select(node);
    }
    group.addEventListener("click", activate);
    group.addEventListener("keydown", function (event) { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); activate(); } });
  }

  function escape(text) {
    return String(text == null ? "" : text).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;"}[c]; });
  }

  function select(node) {
    selected = node;
    draw();
    var path = [];
    for (var step = node; step; step = step.parent) { path.unshift(step.code); }
    var requirements = node.requirements.map(function (entry) {
      return "<li><a href=\"" + recordBase + "r/" + escape(entry.id) + ".html\">" + escape(entry.id) + "</a> " + escape(entry.title) + "</li>";
    }).join("");
    panel.innerHTML =
      "<h3>" + escape(node.code) + " <span class=\"small\">" + escape(node.structural_code || "") + "</span></h3>" +
      "<p><b>" + escape(node.names.en) + "</b><br>" + escape(node.names.zh || "") + "</p>" +
      "<p class=\"small\">" + escape(path.join(" › ")) + "</p>" +
      "<p>Reference <code>" + escape(node.reference) + "</code><br>Kind: " + escape(node.kind) + (node.status !== "active" ? " (" + escape(node.status) + ")" : "") + "</p>" +
      (node.namespaces.length ? "<p>Requirement IDs: " + node.namespaces.map(function (ns) { return "<code>" + escape(ns) + "-REQ-NNN</code>"; }).join(" ") + "</p>"
        : (node.kind === "context" ? "<p>Conditions: <code>" + escape(node.reference) + "-COND-NNN</code></p>" : "<p class=\"hint\">No requirements are allocated to " + escape(node.kind) + " nodes.</p>")) +
      (node.note ? "<p class=\"small\">Note: " + escape(node.note) + "</p>" : "") +
      "<p>" + node.total + " requirements in this subtree" + (node.requirements.length ? ", " + node.requirements.length + " here:" : ".") + "</p>" +
      (requirements ? "<ul class=\"plain\">" + requirements + "</ul>" : "");
    try { history.replaceState(null, "", "#" + node.reference); } catch (error) { /* file URLs may refuse */ }
  }

  document.getElementById("expand-all").addEventListener("click", function () { collapsed = {}; draw(); });
  document.getElementById("collapse-all").addEventListener("click", function () {
    collapsed = {};
    Object.keys(byReference).forEach(function (reference) {
      var node = byReference[reference];
      if (node.depth >= 1 && node.children.length) { collapsed[reference] = true; }
    });
    draw();
  });

  var start = decodeURIComponent((location.hash || "").slice(1));
  if (start && byReference[start]) {
    for (var step = byReference[start].parent; step; step = step.parent) { collapsed[step.reference] = false; }
    select(byReference[start]);
  } else {
    draw();
  }
})();
