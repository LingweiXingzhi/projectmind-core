"use strict";
(() => {
  const original = window.fetch.bind(window);
  const ready = original("/api/auth/session", {credentials: "same-origin"}).then(async response => {
    if (!response.ok) {location.replace("/login"); throw new Error("请重新登录");}
    const session = await response.json();
    window.projectmindSession = {actor: session.actor, repositories: session.repositories};
    for (const id of ["arch-repo-path", "explorer-repo-path"]) {
      const old = document.getElementById(id);
      if (!old) continue;
      const select = document.createElement("select"); select.id = id; select.className = old.className;
      for (const repo of session.repositories) {
        const option = document.createElement("option"); option.value = repo.key; option.textContent = repo.label;
        select.append(option);
      }
      old.replaceWith(select);
      const label = select.closest("label");
      if (label?.firstChild?.nodeType === Node.TEXT_NODE) label.firstChild.textContent = "服务器仓库";
      const heading = select.closest("form")?.querySelector(".compare-heading");
      if (heading && id === "explorer-repo-path") {
        heading.querySelector("h2").textContent = "选择服务器仓库";
        heading.querySelector("p").textContent = "选择管理员登记的项目；版本可填完整提交 SHA。";
      }
    }
    const bar = document.createElement("div");
    bar.style.cssText = "padding:8px 20px;display:flex;gap:16px;align-items:center;background:#eef3fc";
    const name = document.createElement("span"); name.textContent = "已登录：" + session.actor;
    const logout = document.createElement("button"); logout.textContent = "退出登录";
    logout.addEventListener("click", async () => {
      const result = await original("/api/auth/logout", {method: "POST", credentials: "same-origin",
        headers: {"X-ProjectMind-CSRF": session.csrf}});
      if (result.ok || result.status === 401) location.replace("/login");
    });
    bar.append(name, logout); document.body.prepend(bar);
    return session;
  });
  window.fetch = async (input, init) => {
    const session = await ready, request = new Request(input, init);
    if (new URL(request.url).origin !== location.origin) return original(request);
    const headers = new Headers(request.headers);
    if (!["GET", "HEAD"].includes(request.method)) headers.set("X-ProjectMind-CSRF", session.csrf);
    const result = await original(new Request(request, {headers, credentials: "same-origin"}));
    if (result.status === 401) location.replace("/login");
    return result;
  };
})();
