const params = new URLSearchParams(location.search);
const chromeView = params.get("vista");
const activePage = params.get("pagina");
const isStandalone = Boolean(chromeView);

const { tr, url, selector } = window.terraLanguage;

function section(name) {
  return isStandalone
    ? url("../?seccion=" + name)
    : "#" + name;
}

function active(name) {
  return activePage === name
    ? ' aria-current="page"'
    : "";
}

const brand = `
  <img src="logo.webp" width="40" height="40" alt="">
  <span translate="no" class="notranslate">
    TerraSprout
  </span>
`;

const header = document.querySelector("[data-site-header]");
const footer = document.querySelector("[data-site-footer]");

// ==========================================
// ENCABEZADO Y MENÚ DE NAVEGACIÓN
// ==========================================

if (header) {
  header.innerHTML = `
    <nav class="wrap" aria-label="Navegación principal">

      <a class="brand"
         href="${isStandalone ? url("../") : "#inicio"}">
        ${brand}
      </a>

      <button
        type="button"
        class="menu-toggle"
        aria-label="${tr("Abrir menú", "Open menu")}"
        aria-expanded="false"
        aria-controls="mobileMenu">

        <span></span>
        <span></span>
        <span></span>

      </button>

      <div class="links" id="mobileMenu">

        <a href="${section("video")}">
          Video
        </a>

        <a href="${section("proyecto")}">
          ${tr("Proyecto", "Project")}
        </a>

        <a href="${section("equipo")}">
          ${tr("Equipo", "Team")}
        </a>

        <a href="${url("../mapa")}"
           target="_top"${active("mapa")}>
          ${tr("Mapa", "Map")}
        </a>

        <div class="header-buttons">

          <button
            type="button"
            class="header-button"
            disabled>
            ${tr("Registrarse", "Sign up")}
          </button>

          <button
            type="button"
            class="header-button header-button-primary"
            disabled>
            ${tr("Iniciar sesión", "Sign in")}
          </button>

        </div>

      </div>

    </nav>
  `;

  // Selector de idioma
  selector(
    header.querySelector(".links"),
    header.querySelector(".header-buttons")
  );

  // Menú responsive
  const menuToggle = header.querySelector(".menu-toggle");
  const mobileMenu = header.querySelector("#mobileMenu");

  function setMenu(open) {
    mobileMenu.classList.toggle("active", open);
    menuToggle.classList.toggle("active", open);

    menuToggle.setAttribute(
      "aria-expanded",
      String(open)
    );

    menuToggle.setAttribute(
      "aria-label",
      open
        ? tr("Cerrar menú", "Close menu")
        : tr("Abrir menú", "Open menu")
    );
  }

  // Abrir y cerrar menú
  menuToggle.addEventListener("click", () => {
    setMenu(!mobileMenu.classList.contains("active"));
  });

  // Cerrar al seleccionar un enlace
  mobileMenu.querySelectorAll("a").forEach(link => {
    link.addEventListener("click", () => {
      setMenu(false);
    });
  });

  // Cerrar al hacer clic fuera del menú
  document.addEventListener("click", event => {
    if (!header.contains(event.target)) {
      setMenu(false);
    }
  });

  // Cerrar con la tecla Escape
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      setMenu(false);
    }
  });

  // Restablecer al regresar a escritorio
  window.addEventListener("resize", () => {
    if (window.innerWidth > 800) {
      setMenu(false);
    }
  });
}

// ==========================================
// SECCIÓN ACTIVA
// ==========================================

if (header && !isStandalone) {

  function markSection() {

    for (const link of header.querySelectorAll(
      '.links a[href^="#"]'
    )) {

      if (link.hash === location.hash) {
        link.setAttribute("aria-current", "location");
      } else {
        link.removeAttribute("aria-current");
      }

    }
  }

  addEventListener("hashchange", markSection);

  markSection();
}

// ==========================================
// PIE DE PÁGINA
// ==========================================

if (footer) {

  footer.innerHTML = `
    <div class="wrap">

      <a class="brand"
         href="${isStandalone ? url("../") : "#inicio"}">
        ${brand}
      </a>

      <p>
        ${tr(
          "Proyecto del reto Field Shift",
          "Field Shift challenge project"
        )}
        · NASA Space Apps Challenge 2026
      </p>

      <nav aria-label="Enlaces del pie de página">

        <a href="${isStandalone ? url("../") : "#inicio"}">
          ${
            isStandalone
              ? tr("Inicio", "Home")
              : tr("Volver arriba ↑", "Back to top ↑")
          }
        </a>

        <a href="${section("proyecto")}">
          ${tr("Proyecto", "Project")}
        </a>

        <a href="${section("video")}">
          Video
        </a>

        <a href="${section("equipo")}">
          ${tr("Equipo", "Team")}
        </a>

        <a href="${url("../mapa")}" target="_top">
          ${tr("Mapa mundial ↗", "World map ↗")}
        </a>

      </nav>

      <p class="footer-credit">
        ${tr(
          "Imágenes Blue Marble de la NASA.",
          "NASA Blue Marble imagery."
        )}
      </p>

    </div>
  `;
}

// ==========================================
// INTEGRACIÓN CON FLET WEBVIEW
// ==========================================

if (isStandalone) {

  document.documentElement.classList.add("chrome-view");

  document.body.classList.add(
    "chrome-view",
    "chrome-" + chromeView
  );

  for (const link of document.querySelectorAll("a")) {
    link.target = "_top";
  }

  if (chromeView === "header") {
    footer?.remove();
  }

  if (chromeView === "footer") {
    header?.remove();
  }
}
