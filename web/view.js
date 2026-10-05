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
// semantics stay exactly as D published them. The frame loads lazily on the
// first tab activation (and explorer.js removes it entirely in no-map mode),
// so a no-map instance never fetches an extension page.
for (const tab of document.querySelectorAll(".collab-tab")) {
  tab.addEventListener("click", () => {
    for (const other of document.querySelectorAll(".collab-tab")) {
      other.classList.toggle("active", other === tab);
    }
    const frame = document.getElementById("collab-frame");
    if (frame) frame.src = tab.dataset.page;
  });
}
