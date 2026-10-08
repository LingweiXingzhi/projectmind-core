const extensionLinks = document.getElementById("extension-links");

async function listExtensions() {
  try {
    const response = await fetch("/api/extensions");
    const result = await response.json();
    if (!response.ok) {
      const detail = typeof result.error === "string"
        ? result.error
        : (result.error && result.error.message) || `HTTP ${response.status}`;
      throw new Error(detail);
    }
    extensionLinks.replaceChildren();
    if (!result.extensions.length) {
      const empty = document.createElement("div");
      empty.className = "extension-nav-note";
      empty.textContent = "暂无扩展";
      extensionLinks.append(empty);
      return;
    }
    for (const extension of result.extensions) {
      if (extension.status === "ready") {
        const link = document.createElement("a");
        link.className = "nav-item extension-nav";
        link.href = extension.pageUrl;
        link.textContent = projectmindUiLabel(extension.title);
        link.title = projectmindUiDescription(extension.description);
        extensionLinks.append(link);
      } else {
        const note = document.createElement("div");
        note.className = "extension-nav-note";
        note.textContent = `${extension.id}：不可用`;
        note.title = extension.note;
        extensionLinks.append(note);
      }
    }
  } catch (error) {
    const note = document.createElement("div");
    note.className = "extension-nav-note";
    note.textContent = `扩展读取失败：${error.message}`;
    extensionLinks.replaceChildren(note);
  }
}

listExtensions();

