// Unified shell navigation: three top-level products (§37 information
// architecture). Extension pages stay reachable under 高级/调试 for raw
// inspection; no backend semantics are redefined here — every view consumes
// the existing APIs as-is.
const VIEW_TITLES = { map: "项目地图", review: "变更审查", collab: "协作交接", explorer: "仓库浏览" };

function activateView(name) {
  for (const section of document.querySelectorAll(".view")) {
    section.hidden = section.id !== `view-${name}`;
  }
  for (const item of document.querySelectorAll(".top-nav .nav-item")) {
    item.classList.toggle("active", item.dataset.view === name);
  }
  const crumb = document.getElementById("breadcrumb-current");
  if (crumb) crumb.textContent = VIEW_TITLES[name] || name;
  if (name === "collab") {
    // 首次进入协作视图即加载当前页签（B1-b-06）；但必须等模式探测确认是
    // 地图模式——探测完成前 explorer.js 会移除无地图实例的 iframe，而地图
    // 实例的补加载由 explorer.js 的探测完成回调负责。
    const frame = document.getElementById("collab-frame");
    if (frame && !frame.getAttribute("src") && frame.dataset.src
        && document.body.dataset.mapMode === "true") {
      const active = document.querySelector(".collab-tab.active");
      frame.src = (active && active.dataset.page) || frame.dataset.src;
    }
  }
}

for (const item of document.querySelectorAll(".top-nav .nav-item")) {
  const select = () => activateView(item.dataset.view);
  item.addEventListener("click", select);
  item.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      select();
    }
  });
}

// 协作交接 view: tab composition over the D extensions' own pages — their
// semantics stay exactly as D published them. Every iframe load entry (nav
// activation and tab clicks alike) is gated on the confirmed map mode
// (B1-b-06); the frame loads lazily and explorer.js removes it entirely in
// no-map mode.
for (const tab of document.querySelectorAll(".collab-tab")) {
  tab.addEventListener("click", () => {
    for (const other of document.querySelectorAll(".collab-tab")) {
      other.classList.toggle("active", other === tab);
    }
    const frame = document.getElementById("collab-frame");
    if (frame && document.body.dataset.mapMode === "true") {
      frame.src = tab.dataset.page;
    }
  });
}
