const irrigationModes = new Set(["rainfed", "gravity", "drip"]);

export function connectCropScene(viewer, stateId) {
  if (!stateId || !/^[a-f0-9]{32}$/.test(stateId)) return;
  // Flet's SharedPreferences web adapter stores JSON values under flutter.*.
  const key = "flutter.terrasprout.crop-scene." + stateId;
  function apply(raw) {
    if (!raw) return;
    let irrigation;
    try { irrigation = JSON.parse(raw); } catch { return; }
    if (!irrigationModes.has(irrigation)) return;
    viewer.setIrrigation(irrigation);
    const updated = new URL(location.href);
    updated.searchParams.set("riego", irrigation);
    history.replaceState(history.state, "", updated.href);
    try {
      if (localStorage.getItem(key) === raw) localStorage.removeItem(key);
    } catch {}
  }
  window.addEventListener("storage", event => {
    if (event.key === key) apply(event.newValue);
  });
  try { apply(localStorage.getItem(key)); } catch {}
}
