const extensionId = location.pathname.split("/").filter(Boolean).at(-1);
const title = document.getElementById("extension-title");
const description = document.getElementById("extension-description");
const runButton = document.getElementById("extension-run");
const status = document.getElementById("extension-status");
const output = document.getElementById("extension-output");

async function runExtension() {
  runButton.disabled = true;
  status.textContent = "正在运行…";
  try {
    const response = await fetch(`/api/extensions/${encodeURIComponent(extensionId)}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "扩展运行失败");
    output.textContent = JSON.stringify(result, null, 2);
    status.textContent = "已返回结果。请按扩展说明核查来源。";
  } catch (error) {
    output.textContent = "";
    status.textContent = `运行失败：${error.message}`;
  } finally {
    runButton.disabled = false;
  }
}

async function initExtension() {
  try {
    const response = await fetch("/api/extensions");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "无法读取扩展");
    const extension = result.extensions.find((item) => item.id === extensionId && item.status === "ready");
    if (!extension) throw new Error("扩展不存在或不可用");
    title.textContent = projectmindUiLabel(extension.title);
    description.textContent = projectmindUiDescription(extension.description);
    runButton.disabled = false;
  } catch (error) {
    title.textContent = "扩展不可用";
    status.textContent = error.message;
  }
}

runButton.addEventListener("click", runExtension);
initExtension();
