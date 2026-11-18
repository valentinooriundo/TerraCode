// TerraCode web: HTML + JS sin compilación. Rutas con hash (#/inicio, #/nuevo, #/registros, #/historial, #/clima).
// Escritorio: barra lateral fija. Celular: pestañas abajo con botón central "Nuevo".
import * as api from "./api.js";

const $app = document.getElementById("app");
const CONFIG = window.TERRACODE_CONFIG || {};

const TIPOS_RIEGO = { SECANO: "Secano (lluvia)", GRAVEDAD: "Riego por gravedad", GOTEO: "Riego por goteo" };
const ICONO_RIEGO = { SECANO: "rainy", GRAVEDAD: "waves", GOTEO: "water_drop" };
const PRECISION_RECOMENDADA = 50;
const MAX_CULTIVOS = 8;
const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"];
const DIAS = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
const MOVIMIENTO_REDUCIDO = matchMedia("(prefers-reduced-motion: reduce)");

const NAV = [
  { ruta: "/inicio", ic: "home", texto: "Inicio" },
  { ruta: "/registros", ic: "fact_check", texto: "Registros" },
  { ruta: "/nuevo", ic: "add_location_alt", texto: "Nuevo registro", corto: "Nuevo", fab: true },
  { ruta: "/historial", ic: "insights", texto: "Historial" },
  { ruta: "/clima", ic: "partly_cloudy_day", texto: "Clima" },
];

// ---------- utilidades ----------------------------------------------------------------------------------------------

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const icono = (nombre, clase = "") => `<span class="ms ${clase}" aria-hidden="true">${nombre}</span>`;
const num = (v, d = 0) => v == null || Number.isNaN(Number(v)) ? "–" : Number(v).toFixed(d);
const esperar = ms => new Promise(ok => setTimeout(ok, ms));

function toast(mensaje, tipo = "") {
  const t = document.getElementById("toast");
  t.innerHTML = `${icono(tipo === "error" ? "error" : "check_circle", "relleno")}<span>${esc(mensaje)}</span>`;
  t.className = `toast ${tipo}`;
  t.hidden = false;
  // Reinicia la animación de entrada
  t.style.animation = "none"; void t.offsetWidth; t.style.animation = "";
  clearTimeout(toast.reloj);
  toast.reloj = setTimeout(() => { t.hidden = true; }, 3500);
}

function aviso(tipo, texto) {
  const ic = { error: "error", atencion: "warning", info: "info", ok: "check_circle" }[tipo] || "info";
  return `<div class="aviso ${tipo}">${icono(ic)}<div>${texto}</div></div>`;
}

function fecha(iso, conHora = true) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const f = `${d.getDate()} ${MESES[d.getMonth()]} ${d.getFullYear()}`;
  return conHora ? `${f}, ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}` : f;
}

function hace(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const min = Math.round((Date.now() - d) / 60000);
  if (min < 1) return "ahora";
  if (min < 60) return `hace ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `hace ${h} h`;
  const dias = Math.round(h / 24);
  if (dias < 7) return dias === 1 ? "ayer" : `hace ${dias} días`;
  return fecha(iso, false);
}

/** Numera los hijos (--i) para que entren escalonados. */
function escalonar(contenedor) {
  [...contenedor.children].forEach((c, i) => c.style.setProperty("--i", Math.min(i, 12)));
}

/** Cuenta hasta el valor de data-contar. */
function contar(raiz) {
  raiz.querySelectorAll("[data-contar]").forEach(el => {
    const fin = Number(el.dataset.contar);
    if (MOVIMIENTO_REDUCIDO.matches || !fin) { el.textContent = fin; return; }
    const t0 = performance.now(), dur = 900;
    const paso = t => {
      const p = Math.min(1, (t - t0) / dur);
      el.textContent = Math.round(fin * (1 - (1 - p) ** 3));
      if (p < 1) requestAnimationFrame(paso);
    };
    requestAnimationFrame(paso);
  });
}

/** Diálogo de confirmación propio (en vez del confirm() del navegador). */
function confirmar({ titulo, texto, aceptar = "Aceptar", icono: ic = "warning" }) {
  return new Promise(ok => {
    const d = document.createElement("dialog");
    d.className = "dialogo";
    d.innerHTML = `<form method="dialog">
      <span class="dialogo-ic">${icono(ic)}</span><h2>${esc(titulo)}</h2><p class="muted">${esc(texto)}</p>
      <div class="fila fin"><button class="btn secundario" value="no">Cancelar</button>
      <button class="btn rojo" value="si">${esc(aceptar)}</button></div></form>`;
    document.body.append(d);
    d.addEventListener("close", () => { ok(d.returnValue === "si"); d.remove(); });
    d.addEventListener("click", ev => { if (ev.target === d) d.close("no"); });
    d.showModal();
  });
}

/** Errores comunes de las pantallas: sesión vencida → login. */
function manejar(e, contenedor) {
  if (e instanceof api.SesionExpirada) {
    toast(e.message, "error");
    location.hash = "#/login";
    return true;
  }
  if (contenedor) contenedor.innerHTML = aviso("error", esc(e.message));
  else toast(e.message, "error");
  return false;
}

function ubicacion() {
  return new Promise((ok, mal) => {
    if (!navigator.geolocation) return mal(new Error("Este navegador no permite obtener la ubicación."));
    navigator.geolocation.getCurrentPosition(
      p => ok({ latitud: p.coords.latitude, longitud: p.coords.longitude, precision: p.coords.accuracy }),
      e => mal(new Error(e.code === 1
        ? "No diste permiso de ubicación. Actívalo en el candado de la barra de direcciones y reintenta."
        : e.code === 3 ? "El GPS tardó demasiado. Sal a cielo abierto y reintenta."
          : "No se pudo obtener la ubicación. Reintenta.")),
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 });
  });
}

const vacio = (ic, texto, extra = "") =>
  `<div class="vacio"><span class="burbuja-grande">${icono(ic)}</span><p>${texto}</p>${extra}</div>`;

// ---------- marco (barra lateral, cabecera, pestañas) ---------------------------------------------------------------

function iniciales(u) {
  const partes = (u.descripcion || u.login || "?").trim().split(/\s+/);
  return ((partes[0]?.[0] || "") + (partes[1]?.[0] || "")).toUpperCase() || "?";
}

async function salir() {
  const ok = await confirmar({ titulo: "¿Cerrar sesión?", texto: "Tendrás que volver a ingresar para ver tus registros.", aceptar: "Cerrar sesión", icono: "logout" });
  if (!ok) return;
  await api.logout();
  location.hash = "#/login";
}

/** Pinta la pantalla dentro del marco (lo crea la primera vez) y devuelve el contenedor .pagina. */
function marco(ruta, titulo, contenido, { acciones = "", subtitulo = "" } = {}) {
  let shell = $app.querySelector(".shell");
  if (!shell) {
    const u = api.sesion()?.usuario || {};
    const enlace = n => `<a href="#${n.ruta}" data-ruta="${n.ruta}">${icono(n.ic)}<span>${n.texto}</span></a>`;
    $app.innerHTML = `<div class="shell">
      <aside class="lateral">
        <a class="logo" href="#/inicio"><img src="icon.svg" alt=""><span>TerraCode</span></a>
        <a class="btn bloque" href="#/nuevo" data-ruta="/nuevo">${icono("add_location_alt")}Nuevo registro</a>
        <nav class="nav-lateral" aria-label="Secciones">
          ${NAV.filter(n => !n.fab).map(enlace).join("")}
          ${CONFIG.explorador ? `<a href="${esc(CONFIG.explorador)}" target="_blank" rel="noopener">${icono("public")}<span>Explorador</span>${icono("open_in_new", "mini externo")}</a>` : ""}
        </nav>
        <div class="perfil"><span class="avatar">${esc(iniciales(u))}</span>
          <div class="perfil-texto"><strong>${esc(u.descripcion || u.login || "")}</strong><span class="muted">@${esc(u.login || "")}</span></div>
          <button class="icono-btn" data-salir aria-label="Cerrar sesión" title="Cerrar sesión">${icono("logout")}</button></div>
      </aside>
      <div class="principal">
        <header class="cabecera">
          <a class="icono-btn atras" href="#/inicio" aria-label="Volver al inicio">${icono("arrow_back")}</a>
          <a class="logo-movil" href="#/inicio" aria-label="TerraCode"><img src="icon.svg" alt=""></a>
          <div class="titulos"><h1 id="titulo"></h1><p id="subtitulo" class="muted chico" hidden></p></div>
          <div id="acciones" class="fila" style="gap:4px"></div>
          <button class="icono-btn solo-movil" data-salir aria-label="Cerrar sesión">${icono("logout")}</button>
        </header>
        <div id="contenido"></div>
      </div>
      <nav class="tabs" aria-label="Secciones">${NAV.map(n => `<a href="#${n.ruta}" data-ruta="${n.ruta}" class="${n.fab ? "fab" : ""}">
        ${n.fab ? `<span class="fab-btn">${icono(n.ic)}</span>` : icono(n.ic)}<span>${n.corto || n.texto}</span></a>`).join("")}</nav>
    </div>`;
    shell = $app.querySelector(".shell");
    shell.querySelectorAll("[data-salir]").forEach(b => b.addEventListener("click", salir));
  }
  shell.querySelectorAll("[data-ruta]").forEach(a => {
    const activo = a.dataset.ruta === ruta;
    a.classList.toggle("activo", activo);
    if (activo) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  shell.classList.toggle("en-inicio", ruta === "/inicio");
  shell.querySelector("#titulo").textContent = titulo;
  const $sub = shell.querySelector("#subtitulo");
  $sub.textContent = subtitulo; $sub.hidden = !subtitulo;
  shell.querySelector("#acciones").innerHTML = acciones;
  const cont = shell.querySelector("#contenido");
  cont.innerHTML = `<div class="pagina vista">${contenido}</div>`;
  const pagina = cont.firstElementChild;
  escalonar(pagina);
  pagina.querySelectorAll(".escalonado").forEach(escalonar);
  document.title = ruta === "/inicio" ? "TerraCode" : `${titulo} · TerraCode`;
  return pagina;
}

// ---------- login ---------------------------------------------------------------------------------------------------

const GOOGLE_SVG = `<svg viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>`;

const BENEFICIOS = [
  ["eco", "Cultivos recomendados", "Según el clima histórico de tu parcela y tu tipo de riego."],
  ["insights", "Tu historial en gráficos", "Registros por cultivo, zona y mes."],
  ["partly_cloudy_day", "Clima de 7 días", "Pronóstico donde estás, para planificar."],
];

function vistaLogin({ mensaje = "", esperandoGoogle = false } = {}) {
  document.title = "Iniciar sesión · TerraCode";
  $app.innerHTML = `<section class="login">
    <div class="login-hero">
      <span class="blob b1"></span><span class="blob b2"></span><span class="blob b3"></span>
      <div class="login-hero-in">
        <a class="logo" href="/"><img src="icon.svg" alt=""><span>TerraCode</span></a>
        <h2>Decide qué sembrar con datos de tu propia parcela.</h2>
        <p class="bajada">Registra tu ubicación y recibe los cultivos con mejor aptitud para tu zona.</p>
        <ul class="beneficios">${BENEFICIOS.map(([ic, t, d], i) => `<li style="--i:${i}">${icono(ic)}<div><strong>${t}</strong><span class="txt">${d}</span></div></li>`).join("")}</ul>
      </div>
    </div>
    <div class="login-panel"><form class="login-form" novalidate>
      ${esperandoGoogle ? `<div class="pulso"><img src="icon.svg" alt=""></div>
        <h1 style="text-align:center">Confirmando con Google…</h1>
        <p class="muted" style="text-align:center">Un momento, estamos preparando tu sesión.</p>` : `
      <div><h1>Bienvenido</h1><p class="muted">Ingresa para continuar.</p></div>
      <div id="mensaje">${mensaje}</div>
      <label class="campo">Usuario<span class="con-icono">${icono("person")}
        <input class="input" name="usuario" autocomplete="username" required autofocus placeholder="Tu usuario"></span></label>
      <label class="campo">Contraseña<span class="con-icono">${icono("lock")}
        <input class="input" name="contrasena" type="password" autocomplete="current-password" required placeholder="••••••••">
        <button type="button" class="icono-btn ver" aria-label="Mostrar contraseña">${icono("visibility")}</button></span></label>
      <button class="btn bloque" type="submit">Iniciar sesión ${icono("arrow_forward")}</button>
      <div class="separador">o continúa con</div>
      <button class="btn google bloque" type="button" id="google">${GOOGLE_SVG}Google</button>
      <div class="enlaces"><a href="/">${icono("home", "mini")}Inicio</a><a href="/descargas/terracode.apk">${icono("download", "mini")}App Android</a></div>`}
    </form></div>
  </section>`;
  if (esperandoGoogle) return;

  const form = $app.querySelector("form");
  const $msg = form.querySelector("#mensaje");
  const ocupado = (btn, si, texto) => {
    form.querySelectorAll("button").forEach(b => { b.disabled = si; });
    if (si) { btn.dataset.html = btn.innerHTML; btn.innerHTML = `<span class="spinner"></span>${texto}`; }
    else if (btn.dataset.html) btn.innerHTML = btn.dataset.html;
  };

  const ver = form.querySelector(".ver");
  ver.addEventListener("click", () => {
    const oculto = form.contrasena.type === "password";
    form.contrasena.type = oculto ? "text" : "password";
    ver.innerHTML = icono(oculto ? "visibility_off" : "visibility");
    ver.setAttribute("aria-label", oculto ? "Ocultar contraseña" : "Mostrar contraseña");
  });

  form.addEventListener("submit", async ev => {
    ev.preventDefault();
    const usuario = form.usuario.value.trim(), contrasena = form.contrasena.value;
    if (!usuario || !contrasena) { $msg.innerHTML = aviso("error", "Escribe tu usuario y contraseña."); return; }
    const btn = form.querySelector("[type=submit]");
    ocupado(btn, true, "Entrando…");
    try {
      await api.login(usuario, contrasena);
      location.hash = "#/inicio";
    } catch (e) {
      $msg.innerHTML = aviso("error", esc(e.message));
      ocupado(btn, false);
      form.contrasena.select();
    }
  });

  form.querySelector("#google").addEventListener("click", async ev => {
    const btn = ev.currentTarget;
    ocupado(btn, true, "Abriendo Google…");
    try { await api.iniciarGoogle(); } catch (e) { $msg.innerHTML = aviso("error", esc(e.message)); ocupado(btn, false); }
  });
}

async function volverDeGoogle(resultado) {
  // Quita ?google=... de la URL para que recargar no repita el canje
  history.replaceState(null, "", location.pathname + "#/inicio");
  vistaLogin({ esperandoGoogle: true });
  try {
    await api.retomarGoogle(resultado);
    ir();
  } catch (e) {
    history.replaceState(null, "", "#/login");
    vistaLogin({ mensaje: aviso("error", esc(e.message)) });
  }
}

// ---------- inicio --------------------------------------------------------------------------------------------------

function filaMini(r) {
  return `<a class="mini" href="#/registros"><span class="mini-ic">${icono("grass")}</span>
    <span class="mini-texto"><strong>${esc(r.cultivoDescripcion)}</strong>
      <span class="muted chico">${esc(r.zona?.descripcion || "Zona no identificada")} · ${hace(r.fechaRegistro)}</span></span>
    ${r.estado === false ? `<span class="etiqueta gris">Anulado</span>` : r.puntaje != null ? `<span class="etiqueta verde">${num(r.puntaje)}</span>` : ""}</a>`;
}

function vistaInicio() {
  const u = api.sesion()?.usuario || {};
  const nombre = (u.descripcion || u.login || "").split(" ")[0];
  const h = new Date().getHours();
  const saludo = h < 12 ? "Buenos días" : h < 19 ? "Buenas tardes" : "Buenas noches";
  const hoy = new Date().toLocaleDateString("es-PE", { weekday: "long", day: "numeric", month: "long" });
  const opcion = (href, ic, titulo, texto, clase = "", extra = "") =>
    `<a class="opcion interactiva ${clase}" href="${href}" ${extra}><span class="burbuja">${icono(ic)}</span>
      ${icono(extra ? "open_in_new" : "arrow_forward", "flecha")}<h3>${titulo}</h3><span class="muted chico">${texto}</span></a>`;

  const $p = marco("/inicio", "Inicio", `
    <section class="hero">
      <div class="hero-texto"><p class="hero-fecha">${esc(hoy)}</p>
        <h2>${saludo}${nombre ? `, ${esc(nombre)}` : ""}</h2>
        <p>¿Qué vas a registrar hoy en el campo?</p>
        <a class="btn claro" href="#/nuevo">${icono("add_location_alt")}Nuevo registro</a></div>
      <div class="hero-deco" aria-hidden="true">${icono("eco")}</div>
    </section>
    <div class="home-grid">
      <section class="columna"><h2 class="seccion">Accesos</h2>
        <nav class="menu escalonado">
          ${opcion("#/registros", "fact_check", "Mis registros", "Revisa o anula lo que registraste")}
          ${opcion("#/historial", "insights", "Historial", "Resumen por cultivo, zona y mes", "ambar")}
          ${opcion("#/clima", "partly_cloudy_day", "Clima", "Pronóstico de 7 días donde estás", "azul")}
          ${CONFIG.explorador ? opcion(esc(CONFIG.explorador), "public", "Explorador", "Mapa y asistente de TerraSprout", "violeta", 'target="_blank" rel="noopener"') : ""}
        </nav></section>
      <section class="tarjeta columna" style="gap:8px">
        <div class="fila entre"><h2>Actividad reciente</h2><a class="enlace" href="#/registros">Ver todo${icono("chevron_right", "mini")}</a></div>
        <div id="recientes" class="columna" style="gap:4px">${Array.from({ length: 4 }, () =>
    `<div class="fila" style="padding:10px 0"><div class="esqueleto" style="width:40px;height:40px"></div>
          <div style="flex:1" class="columna"><div class="esqueleto" style="width:60%;height:12px"></div><div class="esqueleto" style="width:40%;height:10px"></div></div></div>`).join("")}</div>
      </section>
    </div>`);

  const $r = $p.querySelector("#recientes");
  api.registros({ page: 0, size: 5 }).then(d => {
    const items = d?.content || [];
    $r.innerHTML = items.length ? items.map(filaMini).join("")
      : vacio("grass", "Aún no tienes registros.", `<a class="btn chico" href="#/nuevo">${icono("add")}Crear el primero</a>`);
    $r.classList.add("escalonado"); escalonar($r);
  }).catch(e => manejar(e, $r));
}

// ---------- nuevo registro ------------------------------------------------------------------------------------------

const FASES = ["Ubicando tu zona…", "Revisando el clima histórico…", "Calculando la aptitud de cada cultivo…", "Ya casi está…"];

function vistaNuevo() {
  const st = { pos: null, rec: null, riego: "SECANO", analizado: null };
  const $p = marco("/nuevo", "Nuevo registro", `
    <div class="dos-col">
      <div class="columna escalonado">
        <section class="tarjeta columna paso" id="paso-ubic">
          <div class="tarjeta-titulo"><span class="paso-num">1</span><h2>Ubicación de la parcela</h2></div>
          <div id="ubic"><p class="muted chico">Párate dentro de la parcela y toca el botón. Funciona mejor en el celular, a cielo abierto.</p></div>
          <button class="btn secundario" id="btn-ubic">${icono("my_location")}Obtener mi ubicación</button>
        </section>
        <section class="tarjeta columna paso" id="paso-riego">
          <div class="tarjeta-titulo"><span class="paso-num">2</span><h2>Tipo de riego</h2></div>
          <div class="segmentos" role="radiogroup" aria-label="Tipo de riego">${Object.entries(TIPOS_RIEGO).map(([k, v]) =>
    `<label><input type="radio" name="riego" value="${k}" ${k === st.riego ? "checked" : ""}>${icono(ICONO_RIEGO[k])}${v}</label>`).join("")}</div>
          <button class="btn" id="btn-analizar" disabled>${icono("eco")}Analizar cultivos</button>
        </section>
      </div>
      <div id="resultado" class="columna pegado">
        <section class="tarjeta">${vacio("agriculture", "Ubica tu parcela y analiza para ver los cultivos recomendados.")}</section>
      </div>
    </div>`);

  const $ubic = $p.querySelector("#ubic"), $res = $p.querySelector("#resultado");
  const btnUbic = $p.querySelector("#btn-ubic"), btnAnalizar = $p.querySelector("#btn-analizar");

  btnUbic.addEventListener("click", async () => {
    btnUbic.disabled = true;
    btnUbic.innerHTML = `<span class="spinner"></span>Buscando señal GPS…`;
    try {
      st.pos = await ubicacion();
      const p = st.pos, d = 0.004;
      $ubic.innerHTML = `<div class="columna" style="gap:10px">
        <iframe class="mapa" title="Mapa de la ubicación" loading="lazy"
          src="https://www.openstreetmap.org/export/embed.html?bbox=${p.longitud - d},${p.latitud - d},${p.longitud + d},${p.latitud + d}&layer=mapnik&marker=${p.latitud},${p.longitud}"></iframe>
        <div class="fila entre"><span class="coords">${p.latitud.toFixed(6)}, ${p.longitud.toFixed(6)}</span>
          <span class="etiqueta ${p.precision > PRECISION_RECOMENDADA ? "" : "verde"}">±${num(p.precision)} m</span></div>
        ${p.precision > PRECISION_RECOMENDADA ? aviso("atencion", "Ubicación poco precisa. Acércate al centro de la parcela, o usa el celular, y reintenta.") : ""}</div>`;
      $p.querySelector("#paso-ubic").classList.add("listo");
      btnUbic.innerHTML = `${icono("refresh")}Volver a ubicar`;
      btnAnalizar.disabled = false;
      st.rec = null;
    } catch (e) {
      $ubic.innerHTML = aviso("error", esc(e.message));
      btnUbic.innerHTML = `${icono("my_location")}Reintentar`;
    } finally {
      btnUbic.disabled = false;
    }
  });

  $p.querySelectorAll("input[name=riego]").forEach(r => r.addEventListener("change", () => {
    st.riego = r.value;
    if (st.rec && st.analizado !== st.riego) {
      $res.innerHTML = `<section class="tarjeta">${aviso("info", "Cambiaste el tipo de riego: vuelve a analizar para actualizar los cultivos.")}</section>`;
      st.rec = null;
    }
  }));

  btnAnalizar.addEventListener("click", async () => {
    if (!st.pos) return;
    btnAnalizar.disabled = btnUbic.disabled = true;
    $res.innerHTML = `<section class="tarjeta"><div class="analizando">
      <span class="orbe">${icono("eco")}</span><p class="fase" id="fase">${FASES[0]}</p>
      <p class="muted chico">La primera vez en una zona puede tardar hasta un minuto.</p></div></section>`;
    let f = 0;
    const reloj = setInterval(() => {
      const $f = $res.querySelector("#fase");
      if (!$f) return;
      f = Math.min(f + 1, FASES.length - 1);
      $f.textContent = FASES[f];
      $f.style.animation = "none"; void $f.offsetWidth; $f.style.animation = "";
    }, 4500);
    try {
      st.rec = await api.recomendaciones(st.pos.latitud, st.pos.longitud, st.riego);
      st.analizado = st.riego;
      $p.querySelector("#paso-riego").classList.add("listo");
      pintarResultado();
      if (innerWidth < 960) $res.scrollIntoView({ behavior: MOVIMIENTO_REDUCIDO.matches ? "auto" : "smooth", block: "start" });
    } catch (e) {
      manejar(e, $res);
    } finally {
      clearInterval(reloj);
      btnAnalizar.disabled = btnUbic.disabled = false;
    }
  });

  function pintarResultado() {
    const rec = st.rec, z = rec.zona || {};
    const cultivos = (rec.cultivos || []).slice(0, MAX_CULTIVOS);
    const detalle = [["Distrito", z.distrito], ["Provincia", z.provincia], ["Departamento", z.departamento], ["País", z.pais]]
      .filter(([, v]) => v).map(([k, v]) => `${k}: ${esc(v)}`).join(" · ");
    const nivel = p => p >= 70 ? "" : p >= 40 ? "medio" : "bajo";
    $res.innerHTML = `
    <section class="tarjeta columna" style="gap:6px">
      <div class="tarjeta-titulo">${icono("place")}<h2>${esc(z.descripcion || "Zona no identificada")}</h2></div>
      ${detalle ? `<p class="muted chico">${detalle}</p>` : ""}
    </section>
    <form class="tarjeta columna" id="form-registro">
      <div class="tarjeta-titulo"><span class="paso-num">3</span><h2>Elige el cultivo</h2></div>
      ${cultivos.length ? `<p class="muted chico">Aptitud de 0 a 100 estimada con el clima ${esc(rec.periodoReferencia || "")}${rec.errorMedio != null ? ` (margen de error ±${num(rec.errorMedio, 1)} puntos)` : ""}.</p>` : aviso("atencion", "El modelo no encontró cultivos para esta zona. Puedes registrar otro cultivo.")}
      <div class="columna escalonado" style="gap:10px">
      ${cultivos.map((c, i) => `<label class="cultivo" style="--i:${i}"><input type="radio" name="cultivo" value="${esc(c.codigo)}" ${i === 0 ? "checked" : ""}>
        <div class="nombre"><div class="fila" style="gap:8px;flex-wrap:wrap"><span class="negrita">${esc(c.descripcion)}</span>${i === 0 ? `<span class="etiqueta">${icono("star")}Sugerido</span>` : ""}</div>
          <div class="barra-puntaje ${nivel(c.puntaje)}"><span style="width:${Math.max(0, Math.min(100, c.puntaje || 0))}%;--i:${i}"></span></div></div>
        <span class="puntaje">${num(c.puntaje)}</span></label>`).join("")}
      <label class="cultivo"><input type="radio" name="cultivo" value="__otro" ${cultivos.length ? "" : "checked"}><div class="nombre negrita">Otro cultivo</div>${icono("edit", "mini")}</label>
      </div>
      <label class="campo" id="campo-otro" hidden>Nombre del cultivo<input class="input" name="otro" maxlength="100" placeholder="Por ejemplo: Palta Hass"></label>
      <label class="campo">Observación <span class="muted chico" style="font-weight:400">(opcional)</span><textarea class="input" name="observacion" maxlength="500" placeholder="Estado del terreno, fecha de siembra, etc."></textarea></label>
      <div id="msg-guardar"></div>
      <button class="btn acento" type="submit">${icono("check_circle")}Guardar registro</button>
    </form>`;
    escalonar($res);
    escalonar($res.querySelector(".escalonado"));

    const form = $res.querySelector("#form-registro"), campoOtro = form.querySelector("#campo-otro");
    const actualizarOtro = () => {
      campoOtro.hidden = form.cultivo.value !== "__otro";
      if (!campoOtro.hidden) form.otro.focus();
    };
    form.querySelectorAll("input[name=cultivo]").forEach(r => r.addEventListener("change", actualizarOtro));
    campoOtro.hidden = form.cultivo.value !== "__otro";

    form.addEventListener("submit", async ev => {
      ev.preventDefault();
      const $m = form.querySelector("#msg-guardar"), elegido = form.cultivo.value;
      let codigo = null, descripcion, puntaje = null, sugerido = false;
      if (elegido === "__otro") {
        descripcion = form.otro.value.trim();
        if (!descripcion) { $m.innerHTML = aviso("error", "Escribe el nombre del cultivo."); form.otro.focus(); return; }
      } else {
        const c = cultivos.find(x => String(x.codigo) === elegido);
        codigo = c.codigo; descripcion = c.descripcion; puntaje = c.puntaje;
        sugerido = cultivos[0]?.codigo === c.codigo;
      }
      const btn = form.querySelector("[type=submit]");
      btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>Guardando…`;
      try {
        await api.guardarRegistro({
          latitud: st.pos.latitud, longitud: st.pos.longitud, precisionMetros: st.pos.precision,
          zona: rec.zona, tipoRiego: st.analizado, cultivoCodigo: codigo, cultivoDescripcion: descripcion,
          puntaje, sugerido, observacion: form.observacion.value.trim() || null,
        });
        toast("Registro guardado");
        location.hash = "#/registros";
      } catch (e) {
        if (!manejar(e, $m)) { btn.disabled = false; btn.innerHTML = `${icono("check_circle")}Guardar registro`; }
      }
    });
  }
}

// ---------- mis registros -------------------------------------------------------------------------------------------

function tarjetaRegistro(r, i = 0) {
  const anulado = r.estado === false;
  return `<article class="tarjeta plana registro ${anulado ? "anulado" : ""}" data-id="${esc(r.id)}" style="--i:${Math.min(i, 12)}">
    <div class="cabeza"><span class="mini-ic">${icono("grass")}</span>
      <div style="flex:1;min-width:0"><h3>${esc(r.cultivoDescripcion)}</h3>
        <p class="muted chico">${esc(r.zona?.descripcion || "Zona no identificada")}</p></div>
      <span class="estado-reg">${anulado ? `<span class="etiqueta gris">Anulado</span>` : r.sugerido ? `<span class="etiqueta verde">${icono("star", "mini")}Sugerido</span>` : ""}</span></div>
    <div class="datos-reg">
      <span>${icono("calendar_today")}${fecha(r.fechaRegistro)}</span>
      <span>${icono(ICONO_RIEGO[r.tipoRiego] || "water_drop")}${esc(TIPOS_RIEGO[r.tipoRiego] || r.tipoRiego || "")}</span>
      ${r.puntaje != null ? `<span>${icono("eco")}Aptitud ${num(r.puntaje)}/100</span>` : ""}
    </div>
    ${r.observacion ? `<p class="obs">${esc(r.observacion)}</p>` : ""}
    <div class="acciones">
      <a class="btn secundario chico" target="_blank" rel="noopener" href="https://www.google.com/maps?q=${r.latitud},${r.longitud}">${icono("map")}Ver mapa</a>
      ${anulado ? "" : `<button class="btn peligro chico" data-anular>${icono("delete")}Anular</button>`}
    </div></article>`;
}

function vistaRegistros() {
  const st = { pagina: 0, ultima: false, total: 0 };
  const esqueleto = Array.from({ length: 4 }, () => `<div class="tarjeta plana columna">
    <div class="fila"><div class="esqueleto" style="width:44px;height:44px"></div><div class="columna" style="flex:1;gap:8px">
    <div class="esqueleto" style="width:50%;height:14px"></div><div class="esqueleto" style="width:70%;height:10px"></div></div></div>
    <div class="esqueleto" style="height:10px;width:80%"></div><div class="esqueleto" style="height:34px;width:45%"></div></div>`).join("");
  const $p = marco("/registros", "Mis registros", `
    <div class="fila entre" style="flex-wrap:wrap"><div class="resumen" id="resumen"></div>
      <a class="btn chico" href="#/nuevo">${icono("add")}Nuevo</a></div>
    <div id="lista" class="grilla">${esqueleto}</div><div id="pie"></div>`);
  const $lista = $p.querySelector("#lista"), $pie = $p.querySelector("#pie");

  async function cargar() {
    if (st.pagina > 0) $pie.innerHTML = `<div class="cargando"><span class="spinner"></span>Cargando…</div>`;
    try {
      const d = await api.registros({ page: st.pagina, size: 20 });
      const items = d?.content || [];
      if (st.pagina === 0) {
        $lista.innerHTML = "";
        st.total = d?.totalElements ?? items.length;
        $p.querySelector("#resumen").innerHTML = st.total ? `<span class="chip"><strong>${st.total}</strong> registros</span>` : "";
      }
      if (st.pagina === 0 && !items.length) {
        $lista.outerHTML = `<div id="lista">${vacio("grass", "Todavía no tienes registros.", `<a class="btn" href="#/nuevo">${icono("add_location_alt")}Nuevo registro</a>`)}</div>`;
      } else {
        $lista.insertAdjacentHTML("beforeend", items.map(tarjetaRegistro).join(""));
        $lista.classList.add("escalonado");
      }
      st.ultima = d?.last ?? true;
      $pie.innerHTML = st.ultima ? "" : `<button class="btn secundario bloque" id="mas">${icono("expand_more")}Cargar más</button>`;
    } catch (e) {
      if (st.pagina === 0) $lista.innerHTML = "";
      manejar(e, $pie);
    }
  }

  // El listener va en .pagina (se reemplaza con la vista), no en #app, para no acumularse al navegar
  $p.addEventListener("click", async ev => {
    if (ev.target.closest("#mas")) { st.pagina++; cargar(); return; }
    const btn = ev.target.closest("[data-anular]");
    if (!btn) return;
    const tarjeta = btn.closest("[data-id]");
    const ok = await confirmar({
      titulo: "¿Anular este registro?", texto: "Seguirá en tu lista marcado como anulado y no contará en el historial.",
      aceptar: "Anular", icono: "delete",
    });
    if (!ok) return;
    btn.disabled = true;
    try {
      await api.anularRegistro(tarjeta.dataset.id);
      tarjeta.classList.add("anulado");
      btn.remove();
      tarjeta.querySelector(".estado-reg").innerHTML = `<span class="etiqueta gris">Anulado</span>`;
      toast("Registro anulado");
    } catch (e) {
      btn.disabled = false;
      manejar(e);
    }
  });
  cargar();
}

// ---------- historial -----------------------------------------------------------------------------------------------

function agrupar(valores, max = 6) {
  const cuenta = new Map();
  valores.forEach(v => cuenta.set(v, (cuenta.get(v) || 0) + 1));
  const orden = [...cuenta.entries()].sort((a, b) => b[1] - a[1]);
  if (orden.length <= max) return orden;
  const resto = orden.slice(max - 1).reduce((s, [, n]) => s + n, 0);
  return [...orden.slice(0, max - 1), ["Otros", resto]];
}

function barras(pares, total) {
  const max = Math.max(1, ...pares.map(([, n]) => n));
  return `<div class="barras">${pares.map(([k, n], i) => `<div class="item" title="${esc(k)}: ${n} de ${total}">
    <span class="nombre">${esc(k)}</span><div class="pista"><span style="width:${(n / max) * 100}%;--i:${i}"></span></div>
    <span class="num">${n}</span></div>`).join("")}</div>`;
}

async function vistaHistorial() {
  const $p = marco("/historial", "Historial", `<div id="cont" class="columna">
    <div class="tiles">${Array.from({ length: 4 }, () => `<div class="tile"><div class="esqueleto" style="width:38px;height:38px"></div><div class="esqueleto" style="width:50%;height:26px"></div><div class="esqueleto" style="width:70%;height:10px"></div></div>`).join("")}</div>
    <div class="tarjeta"><div class="esqueleto" style="height:180px"></div></div></div>`);
  const $c = $p.querySelector("#cont");
  let todos = [];
  try {
    for (let page = 0; page < 10; page++) {
      const d = await api.registros({ page, size: 100 });
      todos = todos.concat(d?.content || []);
      if (d?.last ?? true) break;
    }
  } catch (e) { manejar(e, $c); return; }

  const activos = todos.filter(r => r.estado !== false);
  const n = activos.length;
  if (!n) {
    $c.innerHTML = `<section class="tarjeta">${vacio("history", "Aún no hay registros activos para resumir.", `<a class="btn" href="#/nuevo">${icono("add_location_alt")}Nuevo registro</a>`)}</section>`;
    return;
  }
  const cultivos = agrupar(activos.map(r => r.cultivoDescripcion || "—"));
  const deptos = agrupar(activos.map(r => r.zona?.departamento || "Sin departamento"));
  const riegos = agrupar(activos.map(r => TIPOS_RIEGO[r.tipoRiego] || r.tipoRiego || "—"));
  const puntajes = activos.map(r => r.puntaje).filter(p => p != null);
  const sugeridos = activos.filter(r => r.sugerido).length;
  const pctSugeridos = Math.round((sugeridos / n) * 100);

  // Últimos 6 meses, incluido el actual
  const hoy = new Date(), meses = [];
  for (let i = 5; i >= 0; i--) {
    const d = new Date(hoy.getFullYear(), hoy.getMonth() - i, 1);
    meses.push({ clave: `${d.getFullYear()}-${d.getMonth()}`, nombre: MESES[d.getMonth()], n: 0 });
  }
  activos.forEach(r => {
    const d = new Date(r.fechaRegistro);
    const m = meses.find(x => x.clave === `${d.getFullYear()}-${d.getMonth()}`);
    if (m) m.n++;
  });
  const maxMes = Math.max(1, ...meses.map(m => m.n));
  const distintos = new Set(activos.map(r => r.cultivoDescripcion)).size;
  const deptosDistintos = new Set(activos.map(r => r.zona?.departamento).filter(Boolean)).size;
  const promedio = puntajes.length ? Math.round(puntajes.reduce((a, b) => a + b, 0) / puntajes.length) : null;
  const tile = (ic, valor, texto) => `<div class="tile"><span class="tile-ic">${icono(ic)}</span>
    <span class="valor" ${valor != null ? `data-contar="${valor}"` : ""}>${valor != null ? 0 : "–"}</span><span class="muted chico">${texto}</span></div>`;

  $c.innerHTML = `
    <div class="tiles escalonado">
      ${tile("fact_check", n, "Registros activos")}
      ${tile("eco", distintos, "Cultivos distintos")}
      ${tile("place", deptosDistintos, "Departamentos")}
      ${tile("insights", promedio, "Aptitud promedio")}
    </div>
    <div class="graficos">
      <section class="tarjeta columna"><h2>Registros por mes</h2>
        <div class="columnas">${meses.map((m, i) => `<div class="col ${i === 5 ? "actual" : ""}" title="${m.nombre}: ${m.n}"><div class="alto" data-n="${m.n}" style="height:${(m.n / maxMes) * 100}%;--i:${i}"></div>${m.nombre}</div>`).join("")}</div>
      </section>
      <section class="tarjeta columna"><h2>Por cultivo</h2>${barras(cultivos, n)}</section>
      <section class="tarjeta columna"><h2>Por departamento</h2>${barras(deptos, n)}</section>
      <section class="tarjeta columna"><h2>Por tipo de riego</h2>${barras(riegos, n)}
        <div class="fila" style="margin-top:4px"><span class="anillo" style="--p:${pctSugeridos}">${pctSugeridos}%</span>
          <p class="muted chico">Elegiste el cultivo sugerido en ${sugeridos} de ${n} registros.</p></div></section>
      <section class="tarjeta columna ancho"><h2>Últimos registros</h2>
        <ul class="linea-tiempo">${activos.slice(0, 8).map(r => `<li><span class="punto"></span><div>
          <p class="negrita">${esc(r.cultivoDescripcion)}</p>
          <p class="muted chico">${fecha(r.fechaRegistro)} · ${esc(r.zona?.descripcion || "Zona no identificada")}</p></div></li>`).join("")}</ul>
      </section>
    </div>`;
  $c.classList.add("escalonado");
  escalonar($c);
  escalonar($c.querySelector(".tiles"));
  escalonar($c.querySelector(".graficos"));
  $c.querySelector(".graficos").classList.add("escalonado");
  contar($c);
}

// ---------- clima ---------------------------------------------------------------------------------------------------

const TIEMPO = {
  0: ["Despejado", "sunny"], 1: ["Mayormente despejado", "sunny"], 2: ["Parcialmente nublado", "partly_cloudy_day"],
  3: ["Nublado", "cloud"], 45: ["Niebla", "foggy"], 48: ["Niebla con escarcha", "foggy"],
  51: ["Llovizna ligera", "rainy"], 53: ["Llovizna", "rainy"], 55: ["Llovizna intensa", "rainy"],
  56: ["Llovizna helada", "weather_snowy"], 57: ["Llovizna helada intensa", "weather_snowy"],
  61: ["Lluvia ligera", "rainy"], 63: ["Lluvia", "rainy"], 65: ["Lluvia intensa", "rainy"],
  66: ["Lluvia helada", "weather_snowy"], 67: ["Lluvia helada intensa", "weather_snowy"],
  71: ["Nevada ligera", "weather_snowy"], 73: ["Nevada", "weather_snowy"], 75: ["Nevada intensa", "weather_snowy"],
  77: ["Granizo fino", "weather_snowy"], 80: ["Chubascos ligeros", "umbrella"], 81: ["Chubascos", "umbrella"],
  82: ["Chubascos fuertes", "umbrella"], 85: ["Chubascos de nieve", "weather_snowy"], 86: ["Chubascos de nieve fuertes", "weather_snowy"],
  95: ["Tormenta", "thunderstorm"], 96: ["Tormenta con granizo", "thunderstorm"], 99: ["Tormenta con granizo fuerte", "thunderstorm"],
};
const tiempo = c => TIEMPO[c] || ["Sin dato", "cloud"];
const cielo = c => c <= 1 ? "cielo-sol" : c <= 48 ? "cielo-nube" : c >= 95 ? "cielo-tormenta" : "cielo-lluvia";

async function vistaClima() {
  const $p = marco("/clima", "Clima", `<div id="cont"></div>`, {
    acciones: `<button class="icono-btn" id="recargar" aria-label="Actualizar" title="Actualizar">${icono("refresh")}</button>`,
  });
  const $c = $p.querySelector("#cont");
  document.getElementById("recargar").addEventListener("click", cargar);

  async function cargar() {
    $c.innerHTML = `<div class="clima-grid"><div class="tarjeta"><div class="analizando"><span class="orbe">${icono("my_location")}</span>
      <p class="fase" id="fase">Obteniendo tu ubicación…</p></div></div>
      <div class="tarjeta columna">${Array.from({ length: 5 }, () => `<div class="esqueleto" style="height:22px"></div>`).join("")}</div></div>`;
    let p;
    try { p = await ubicacion(); } catch (e) { $c.innerHTML = aviso("error", esc(e.message)); return; }
    const $f = $c.querySelector("#fase");
    if ($f) $f.textContent = "Consultando el pronóstico…";
    const q = new URLSearchParams({
      latitude: p.latitud.toFixed(4), longitude: p.longitud.toFixed(4), timezone: "auto", forecast_days: 7,
      current: "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
      daily: "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max",
    });
    let d;
    try {
      const r = await fetch(`https://api.open-meteo.com/v1/forecast?${q}`);
      if (!r.ok) throw new Error();
      d = await r.json();
    } catch {
      $c.innerHTML = aviso("error", "No se pudo consultar el pronóstico. Revisa tu conexión y reintenta.");
      return;
    }
    const a = d.current, dl = d.daily;
    const [desc, ic] = tiempo(a.weather_code);
    const minS = Math.min(...dl.temperature_2m_min), maxS = Math.max(...dl.temperature_2m_max), rango = Math.max(1, maxS - minS);
    $c.innerHTML = `<div class="clima-grid escalonado">
      <div class="columna">
        <section class="clima-actual ${cielo(a.weather_code)}">
          <div class="fila entre" style="align-items:flex-start"><div><p class="muted chico">Ahora · ${new Date().toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" })}</p>
            <p class="temp"><span data-contar="${Math.round(a.temperature_2m)}">0</span>°</p>
            <p class="negrita" style="font-size:18px;margin-top:6px">${desc}</p><p class="muted chico">Sensación ${num(a.apparent_temperature)}°</p></div>
            ${icono(ic, "grande")}</div>
          <div class="datos">
            <div><span class="muted">Humedad</span><strong>${num(a.relative_humidity_2m)}%</strong></div>
            <div><span class="muted">Lluvia</span><strong>${num(a.precipitation, 1)} mm</strong></div>
            <div><span class="muted">Viento</span><strong>${num(a.wind_speed_10m)} km/h</strong></div>
          </div>
        </section>
        <p class="muted chico">${icono("place", "mini")} ${p.latitud.toFixed(3)}, ${p.longitud.toFixed(3)} · ${esc(d.timezone || "")} · Datos de Open-Meteo</p>
      </div>
      <section class="tarjeta"><h2 style="margin-bottom:6px">Próximos 7 días</h2>
        ${dl.time.map((t, i) => {
      const f = new Date(`${t}T12:00:00`), [dd, di] = tiempo(dl.weather_code[i]);
      const mn = dl.temperature_2m_min[i], mx = dl.temperature_2m_max[i];
      return `<div class="dia" title="${dd}">
            <span class="negrita">${i === 0 ? "Hoy" : DIAS[f.getDay()]}</span>${icono(di)}
            <div class="rango"><span class="muted">${num(mn)}°</span><div class="pista"><span style="left:${((mn - minS) / rango) * 100}%;right:${100 - ((mx - minS) / rango) * 100}%;--i:${i}"></span></div><span class="negrita">${num(mx)}°</span></div>
            <span class="lluvia">${icono("water_drop")}${num(dl.precipitation_probability_max[i])}%</span></div>`;
    }).join("")}
      </section></div>`;
    escalonar($c.querySelector(".clima-grid"));
    contar($c);
  }
  cargar();
}

// ---------- rutas ---------------------------------------------------------------------------------------------------

const RUTAS = { "/inicio": vistaInicio, "/nuevo": vistaNuevo, "/registros": vistaRegistros, "/historial": vistaHistorial, "/clima": vistaClima };

function ir() {
  const ruta = location.hash.replace(/^#/, "") || "/inicio";
  if (!api.sesion()) { if (ruta !== "/login") history.replaceState(null, "", "#/login"); vistaLogin(); return; }
  if (ruta === "/login") { history.replaceState(null, "", "#/inicio"); vistaInicio(); return; }
  (RUTAS[ruta] || vistaInicio)();
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", ir);

const google = new URLSearchParams(location.search).get("google");
if (google) volverDeGoogle(google); else ir();
