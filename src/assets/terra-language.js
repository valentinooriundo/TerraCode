(() => {
  const supported = ["es", "en"];
  const requested = new URLSearchParams(location.search).get("lang");
  let remembered;
  try { remembered = localStorage.getItem("terra-language"); } catch {}
  const browser = (navigator.languages || [navigator.language || "es"]).map(value => value.toLowerCase().split("-")[0])
    .find(value => supported.includes(value));
  const lang = supported.includes(requested) ? requested
    : supported.includes(remembered) ? remembered : browser || "es";
  document.documentElement.lang = lang;
  const tr = (es, en) => lang === "en" ? en : es;
  const url = (href, language = lang) => {
    const target = new URL(href, location.href);
    target.searchParams.set("lang", language);
    return target.href;
  };
  function selector(target, before = null) {
    const field = document.createElement("span");
    field.className = "language-field";
    const flag = document.createElement("span");
    flag.className = `language-flag flag-${lang}`;
    flag.setAttribute("aria-hidden", "true");
    const control = document.createElement("select");
    control.className = "language-selector";
    control.setAttribute("aria-label", tr("Idioma", "Language"));
    for (const [value, label] of [["es", "Español"], ["en", "English"]]) {
      control.add(new Option(label, value, false, value === lang));
    }
    control.addEventListener("change", () => {
      try { localStorage.setItem("terra-language", control.value); } catch {}
      const current = new URL(window.top.location.href);
      if (location.pathname.endsWith("/inicio.html") && location.hash) {
        current.searchParams.set("seccion", location.hash.slice(1));
      }
      window.top.location.href = url(current.href, control.value);
    });
    field.append(flag, control);
    target.insertBefore(field, before);
  }
  window.terraLanguage = { lang, tr, url, selector };
})();
