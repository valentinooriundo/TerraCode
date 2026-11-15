const launcher = document.querySelector(".assistant-globe");

// Remove launch flags left in the address bar by the previous version.
try {
  const host = window.top;
  const url = new URL(host.location.href);
  if (url.origin === location.origin && url.searchParams.get("asistente") === "1") {
    url.searchParams.delete("asistente");
    url.searchParams.delete("apertura");
    host.history.replaceState(host.history.state, "", url.href);
  }
} catch {
  // A separately embedded page may not have access to the host address.
}

if (launcher && typeof HTMLDialogElement !== "undefined") {
  const dialog = document.createElement("dialog");
  dialog.className = "assistant-dialog";
  dialog.setAttribute("aria-label", "Asistente agrícola");

  const close = document.createElement("button");
  close.type = "button";
  close.className = "assistant-close";
  close.setAttribute("aria-label", "Cerrar asistente");
  close.textContent = "×";
  close.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => launcher.focus());
  dialog.append(close);
  document.body.append(dialog);

  launcher.addEventListener("click", event => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (!dialog.querySelector("iframe")) {
      const chat = document.createElement("iframe");
      chat.title = "Chat agrícola de TerraSprout";
      chat.src = launcher.href;
      dialog.append(chat);
    }
    if (!dialog.open) dialog.showModal();
  });
}
