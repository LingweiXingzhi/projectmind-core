"use strict";
document.getElementById("login").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget, error = document.getElementById("error");
  const button = form.querySelector("button"); button.disabled = true; error.textContent = "";
  try {
    const response = await fetch("/api/auth/login", {method: "POST", credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({username: form.username.value, password: form.password.value})});
    form.password.value = "";
    const result = await response.json();
    if (!response.ok) throw new Error(result.error?.message || "登录失败");
    location.replace("/");
  } catch (failure) {error.textContent = failure.message;}
  finally {button.disabled = false;}
});
