(function () {
  "use strict";
  var data = window.QINGSONG_FLOW;
  var canvas = document.getElementById("flow-canvas");
  var filter = document.getElementById("flow-filter");
  if (!data || !canvas) { return; }
  var svgNS = "http://www.w3.org/2000/svg";
  var boxWidth = 168, boxHeight = 44, gap = 14, laneLabel = 150, lanePadding = 16;
  var perRow = Math.max(2, Math.floor((canvas.clientWidth - laneLabel - 2 * gap) / (boxWidth + gap)));
  var maturityColor = {concept: "#9ca3af", draft: "#f59e0b", agreed: "#16a34a", baselined: "#166534"};

  var systems = {};
  data.nodes.forEach(function (node) { systems[node.allocated.split("-")[0]] = true; });
  Object.keys(systems).sort().forEach(function (system) {
    var option = document.createElement("option");
    option.value = system;
    option.textContent = system;
    filter.appendChild(option);
  });

  function element(name, attributes, parent) {
    var node = document.createElementNS(svgNS, name);
    Object.keys(attributes).forEach(function (key) { node.setAttribute(key, attributes[key]); });
    if (parent) { parent.appendChild(node); }
    return node;
  }
  function fit(text, limit) {
    var count = 0, out = "";
    for (var i = 0; i < text.length; i++) {
      count += text.charCodeAt(i) > 0x2e80 ? 2 : 1.05;
      if (count > limit) { return out + "…"; }
      out += text[i];
    }
    return out;
  }

  function draw() {
    var system = filter.value;
    var byId = {};
    data.nodes.forEach(function (node) { byId[node.id] = node; });
    var shown = data.nodes.filter(function (node) {
      if (!system) { return true; }
      if (node.allocated.split("-")[0] === system) { return true; }
      return data.nodes.some(function (other) {
        return other.allocated.split("-")[0] === system && other.parents.indexOf(node.id) >= 0;
      });
    });
    var shownIds = {};
    shown.forEach(function (node) { shownIds[node.id] = true; });
    var position = {};
    var y = lanePadding;
    var lanes = [];
    var maxColumns = 1;
    data.levels.forEach(function (level) {
      var members = shown.filter(function (node) { return node.level === level.name; });
      members.sort(function (a, b) {
        function key(node) {
          var xs = node.parents.filter(function (id) { return position[id]; }).map(function (id) { return position[id].x; });
          return xs.length ? xs.reduce(function (s, v) { return s + v; }, 0) / xs.length : 1e9;
        }
        return key(a) - key(b) || a.id.localeCompare(b.id);
      });
      var rows = Math.max(1, Math.ceil(members.length / perRow));
      var height = rows * (boxHeight + gap) + lanePadding;
      members.forEach(function (node, index) {
        var column = index % perRow, row = Math.floor(index / perRow);
        position[node.id] = {x: laneLabel + gap + column * (boxWidth + gap), y: y + lanePadding / 2 + row * (boxHeight + gap)};
        maxColumns = Math.max(maxColumns, column + 1);
      });
      lanes.push({level: level, y: y, height: height, count: members.length});
      y += height;
    });
    var width = laneLabel + gap + maxColumns * (boxWidth + gap) + gap;
    canvas.innerHTML = "";
    var svg = element("svg", {width: Math.max(width, 640), height: y + lanePadding, "class": "flow", role: "img", "aria-label": "Flow-down of requirements"}, canvas);
    lanes.forEach(function (lane, index) {
      element("rect", {x: 0, y: lane.y, width: Math.max(width, 640), height: lane.height, fill: index % 2 ? "#ffffff" : "#f9fafb"}, svg);
      var label = element("text", {x: 12, y: lane.y + 24, "font-size": 13, "font-weight": "bold", fill: "#1f2937"}, svg);
      label.textContent = lane.level.name.charAt(0).toUpperCase() + lane.level.name.slice(1);
      var full = element("title", {}, label);
      full.textContent = lane.level.names.en;
      var sub = element("text", {x: 12, y: lane.y + 42, "font-size": 12, fill: "#6b7280"}, svg);
      sub.textContent = (lane.level.names.zh || "") + " · " + lane.count;
    });
    var edgeLayer = element("g", {}, svg);
    var nodeLayer = element("g", {}, svg);
    var edges = [];
    shown.forEach(function (node) {
      node.parents.forEach(function (parentId) {
        if (!shownIds[parentId] || !position[parentId]) { return; }
        var from = position[parentId], to = position[node.id];
        var x1 = from.x + boxWidth / 2, y1 = from.y + boxHeight, x2 = to.x + boxWidth / 2, y2 = to.y;
        var suspect = node.suspect.indexOf(parentId) >= 0;
        var path = element("path", {d: "M" + x1 + "," + y1 + " C" + x1 + "," + (y1 + 40) + " " + x2 + "," + (y2 - 40) + " " + x2 + "," + y2,
          fill: "none", stroke: suspect ? "#dc2626" : "#c2410c", "stroke-opacity": 0.55, "stroke-width": 1.6,
          "stroke-dasharray": suspect ? "5 4" : "none"}, edgeLayer);
        edges.push({path: path, child: node.id, parent: parentId});
      });
    });
    var groups = {};
    shown.forEach(function (node) {
      var p = position[node.id];
      var link = element("a", {href: node.url}, nodeLayer);
      var group = element("g", {"class": "fnode", transform: "translate(" + p.x + "," + p.y + ")"}, link);
      element("rect", {width: boxWidth, height: boxHeight, rx: 5, fill: "#ffffff", stroke: "#d1d5db"}, group);
      element("rect", {width: 5, height: boxHeight, rx: 2, fill: maturityColor[node.maturity] || "#9ca3af"}, group);
      var id = element("text", {x: 11, y: 17, "font-size": 11.5, "font-weight": "bold", "font-family": "Menlo, monospace", fill: "#1f2937"}, group);
      id.textContent = node.id;
      var title = element("text", {x: 11, y: 34, "font-size": 11.5, fill: "#374151"}, group);
      title.textContent = fit(node.title.en || node.title.zh || "", 27);
      var tip = element("title", {}, group);
      tip.textContent = node.id + " — " + (node.title.en || "") + " " + (node.title.zh || "") + " (" + node.maturity + ", " + node.allocated + ")";
      groups[node.id] = group;
      group.addEventListener("mouseenter", function () { highlight(node.id); });
      group.addEventListener("mouseleave", function () { highlight(null); });
    });
    function related(id) {
      var up = {}, down = {}, changed = true;
      up[id] = true; down[id] = true;
      while (changed) {
        changed = false;
        edges.forEach(function (edge) {
          if (up[edge.child] && !up[edge.parent]) { up[edge.parent] = true; changed = true; }
          if (down[edge.parent] && !down[edge.child]) { down[edge.child] = true; changed = true; }
        });
      }
      Object.keys(down).forEach(function (key) { up[key] = true; });
      return up;
    }
    function highlight(id) {
      var set = id ? related(id) : null;
      Object.keys(groups).forEach(function (key) { groups[key].classList.toggle("dim", !!set && !set[key]); });
      edges.forEach(function (edge) { edge.path.classList.toggle("dim", !!set && !(set[edge.child] && set[edge.parent])); });
    }
  }
  filter.addEventListener("change", draw);
  draw();
})();
