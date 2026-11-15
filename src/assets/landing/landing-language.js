(() => {
  const { lang, url } = window.terraLanguage;
  for (const link of document.querySelectorAll('a[target="_top"]')) {
    if (link.origin === location.origin) link.href = url(link.href);
  }
  if (lang !== "en") return;
  const english = {
    ".intro": "Explore your plot’s climate with NASA data and compare crop rotations by water demand and soil cover.",
    ".calls a:first-child": "My location", ".calls a:last-child": "Search",
    ".scroll-link": "Explore the project ↓",
    ".story-heading .label": "The project",
    ".story-heading p:not(.label)": "TerraSprout is our Field Shift proposal. It helps farmers explore how crop rotations can adapt to changes in temperature, rainfall, and water availability.",
    ".story-heading a": "View the official challenge ↗",
    ".steps article:nth-child(1) h3": "Find your plot",
    ".steps article:nth-child(1) p": "Search for a place, select a point on the map, or enter coordinates. Draw a boundary to estimate the area.",
    ".steps article:nth-child(1) a": "Open the world map ↗",
    ".steps article:nth-child(2) h3": "Explore climate and satellite imagery",
    ".steps article:nth-child(2) p": "Review seven daily NASA POWER variables for your selected period. TerraSprout looks up ECOSTRESS imagery for your point and shows previews when available.",
    ".steps article:nth-child(3) h3": "Compare crop rotations",
    ".steps article:nth-child(3) p": "Compare three crop sequences using estimated water demand and soil cover.",
    "#video-title": "TerraSprout in 40 seconds",
    "#video p": "From the globe to plot analysis with NASA data.",
    "#equipo .label": "About us",
    "#equipo h2": "The TerraSprout team",
    "#equipo p:not(.label)": "A multidisciplinary team from Ica, Perú, bringing together Earth observation, agricultural science, and technology.",
    "#equipo a": "Meet the team on NASA Space Apps ↗",
  };
  for (const [query, label] of Object.entries(english)) {
    const node = document.querySelector(query);
    if (node) node.textContent = label;
  }
  document.querySelector(".hero h1").firstChild.textContent = "From space";
  document.querySelector(".hero h1 br").nextSibling.textContent = "to the field";
  document.querySelector(".story-heading h2").firstChild.textContent = "One plot,";
  document.querySelector(".story-heading h2 br").nextSibling.textContent = "many scales.";
})();
