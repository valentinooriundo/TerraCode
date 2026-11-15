// TerraCode web: HTML + JS sin compilación. Rutas con hash (#/inicio, #/nuevo, #/registros, #/historial, #/clima).
import * as api from "./api.js";

const $app = document.getElementById("app");
const CONFIG = window.TERRACODE_CONFIG || {};

const TIPOS_RIEGO = { SECANO: "Secano (lluvia)", GRAVEDAD: "Riego por gravedad", GOTEO: "Riego por goteo" };
const PRECISION_RECOMENDADA = 50;
const MAX_CULTIVOS = 8;
const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"];
const DIAS = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];

// ---------- utilidades ----------------------------------------------------------------------------------------------

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const icono = (nombre, clase = "") => `<span class="ms ${clase}" aria-hidden="true">${nombre}</span>`;
const num = (v, d = 0) => v == null || Number.isNaN(Number(v)) ? "–" : Number(v).toFixed(d);

function toast(mensaje, tipo = "") {
  const t = document.getElementById("toast");
  t.textContent = mensaje;
  t.className = `toast ${tipo}`;
  t.hidden = false;
  clearTimeout(toast.reloj);
  toast.reloj = setTimeout(() => { t.hidden = true; }, 3500);
}

function barra(titulo, { atras = true, derecha = "" } = {}) {
  return `<header class="barra">
    ${atras ? `<a class="icono-btn" href="#/inicio" aria-label="Volver">${icono("arrow_back")}</a>` : ""}
    <h1>${esc(titulo)}</h1>${derecha}</header>`;
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

// ---------- login ---------------------------------------------------------------------------------------------------

const GOOGLE_SVG = `<svg viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>`;

function vistaLogin({ mensaje = "", esperandoGoogle = false } = {}) {
  $app.innerHTML = `<section class="login"><form class="tarjeta" novalidate>
    <div class="marca"><img src="icon.svg" alt=""><h1>TerraCode</h1>
      <p class="muted chico">Registra tus parcelas y descubre qué cultivo conviene en tu zona.</p></div>
    <div id="mensaje">${mensaje}</div>
    ${esperandoGoogle ? `<div class="cargando"><span class="spinner"></span>Confirmando con Google…</div>` : `
    <label class="campo">Usuario<input class="input" name="usuario" autocomplete="username" required autofocus></label>
    <label class="campo">Contraseña<input class="input" name="contrasena" type="password" autocomplete="current-password" required></label>
    <button class="btn bloque" type="submit">Iniciar sesión</button>
    <div class="separador">o</div>
    <button class="btn google bloque" type="button" id="google">${GOOGLE_SVG}Continuar con Google</button>
    <div class="enlaces"><a href="/">Inicio</a><a href="/descargas/terracode.apk">${icono("download")} App Android</a></div>`}
  </form></section>`;
  if (esperandoGoogle) return;

  const form = $app.querySelector("form");
  const $msg = form.querySelector("#mensaje");
  const ocupado = (btn, si, texto) => {
    form.querySelectorAll("button").forEach(b => { b.disabled = si; });
    if (si) { btn.dataset.html = btn.innerHTML; btn.innerHTML = `<span class="spinner"></span>${texto}`; }
    else if (btn.dataset.html) btn.innerHTML = btn.dataset.html;
  };

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
    location.hash = "#/login";
    vistaLogin({ mensaje: aviso("error", esc(e.message)) });
  }
}

// ---------- inicio --------------------------------------------------------------------------------------------------

function vistaInicio() {
  const u = api.sesion()?.usuario || {};
  const nombre = (u.descripcion || u.login || "").split(" ")[0];
  const opcion = (href, ic, titulo, texto, clase = "", extra = "") =>
    `<a class="opcion ${clase}" href="${href}" ${extra}><span class="burbuja">${icono(ic)}</span>
      <h3>${titulo}</h3><span class="muted chico">${texto}</span></a>`;
  $app.innerHTML = `${barra("TerraCode", {
    atras: false,
    derecha: `<button class="icono-btn" id="salir" aria-label="Cerrar sesión" title="Cerrar sesión">${icono("logout")}</button>`,
  })}
  <div class="pagina">
    <div class="tarjeta saludo"><h1>Hola${nombre ? `, ${esc(nombre)}` : ""}</h1>
      <p class="muted">¿Qué quieres hacer hoy?</p></div>
    <nav class="menu">
      ${opcion("#/nuevo", "add_location_alt", "Nuevo registro", "Ubica tu parcela y recibe cultivos recomendados", "destacada")}
      ${opcion("#/registros", "fact_check", "Mis registros", "Revisa o anula lo que registraste")}
      ${opcion("#/historial", "insights", "Historial", "Resumen por cultivo, zona y mes")}
      ${opcion("#/clima", "partly_cloudy_day", "Clima", "Pronóstico de 7 días donde estás")}
      ${CONFIG.explorador ? opcion(esc(CONFIG.explorador), "public", "Explorador", "Mapa y asistente de TerraSprout", "", 'target="_blank" rel="noopener"') : ""}
    </nav>
  </div>`;
  $app.querySelector("#salir").addEventListener("click", async () => {
    await api.logout();
    location.hash = "#/login";
  });
}

// ---------- nuevo registro ------------------------------------------------------------------------------------------

function vistaNuevo() {
  const st = { pos: null, rec: null, riego: "SECANO", analizado: null };
  $app.innerHTML = `${barra("Nuevo registro")}
  <div class="pagina">
    <section class="tarjeta columna">
      <div class="fila">${icono("my_location")}<h2>Ubicación</h2></div>
      <div id="ubic"><p class="muted chico">Párate dentro de la parcela y toca el botón.</p></div>
      <button class="btn secundario" id="btn-ubic">${icono("my_location")}Obtener mi ubicación</button>
    </section>
    <section class="tarjeta columna">
      <div class="fila">${icono("water_drop")}<h2>Tipo de riego</h2></div>
      <div class="segmentos" role="radiogroup">${Object.entries(TIPOS_RIEGO).map(([k, v]) =>
    `<label><input type="radio" name="riego" value="${k}" ${k === st.riego ? "checked" : ""}>${v}</label>`).join("")}</div>
      <button class="btn" id="btn-analizar" disabled>${icono("eco")}Analizar cultivos</button>
    </section>
    <div id="resultado" class="columna"></div>
  </div>`;

  const $ubic = $app.querySelector("#ubic"), $res = $app.querySelector("#resultado");
  const btnUbic = $app.querySelector("#btn-ubic"), btnAnalizar = $app.querySelector("#btn-analizar");

  btnUbic.addEventListener("click", async () => {
    btnUbic.disabled = true;
    $ubic.innerHTML = `<div class="fila muted"><span class="spinner"></span>Buscando señal GPS…</div>`;
    try {
      st.pos = await ubicacion();
      const p = st.pos;
      $ubic.innerHTML = `<p class="negrita">${p.latitud.toFixed(6)}, ${p.longitud.toFixed(6)}</p>
        <p class="muted chico">Margen ±${num(p.precision)} m ·
          <a href="https://www.google.com/maps?q=${p.latitud},${p.longitud}" target="_blank" rel="noopener">ver en el mapa</a></p>
        ${p.precision > PRECISION_RECOMENDADA ? aviso("atencion", "Ubicación poco precisa. Para mejorar, acércate al centro de la parcela, o usa el celular, y reintenta.") : ""}`;
      btnUbic.innerHTML = `${icono("refresh")}Volver a ubicar`;
      btnAnalizar.disabled = false;
      st.rec = null; $res.innerHTML = "";
    } catch (e) {
      $ubic.innerHTML = aviso("error", esc(e.message));
    } finally {
      btnUbic.disabled = false;
    }
  });

  $app.querySelectorAll("input[name=riego]").forEach(r => r.addEventListener("change", () => {
    st.riego = r.value;
    if (st.rec && st.analizado !== st.riego) {
      $res.innerHTML = aviso("info", "Cambiaste el tipo de riego: vuelve a analizar para actualizar los cultivos.");
      st.rec = null;
    }
  }));

  btnAnalizar.addEventListener("click", async () => {
    if (!st.pos) return;
    btnAnalizar.disabled = btnUbic.disabled = true;
    $res.innerHTML = `<div class="tarjeta"><div class="cargando"><span class="spinner"></span>
      <span>Analizando el clima histórico de la zona… la primera vez puede tardar hasta un minuto.</span></div></div>`;
    try {
      st.rec = await api.recomendaciones(st.pos.latitud, st.pos.longitud, st.riego);
      st.analizado = st.riego;
      pintarResultado();
    } catch (e) {
      manejar(e, $res);
    } finally {
      btnAnalizar.disabled = btnUbic.disabled = false;
    }
  });

  function pintarResultado() {
    const rec = st.rec, z = rec.zona || {};
    const cultivos = (rec.cultivos || []).slice(0, MAX_CULTIVOS);
    const detalle = [["Distrito", z.distrito], ["Provincia", z.provincia], ["Departamento", z.departamento], ["País", z.pais]]
      .filter(([, v]) => v).map(([k, v]) => `${k}: ${esc(v)}`).join(" · ");
    $res.innerHTML = `
    <section class="tarjeta columna">
      <div class="fila">${icono("place")}<h2>Zona</h2></div>
      <p class="negrita">${esc(z.descripcion || "Zona no identificada")}</p>
      ${detalle ? `<p class="muted chico">${detalle}</p>` : ""}
    </section>
    <form class="tarjeta columna" id="form-registro">
      <div class="fila">${icono("agriculture")}<h2>Cultivo</h2></div>
      ${cultivos.length ? `<p class="muted chico">Aptitud de 0 a 100 estimada con el clima ${esc(rec.periodoReferencia || "")}${rec.errorMedio != null ? ` (margen de error ±${num(rec.errorMedio, 1)} puntos)` : ""}.</p>` : aviso("atencion", "El modelo no encontró cultivos para esta zona. Puedes registrar otro cultivo.")}
      ${cultivos.map((c, i) => `<label class="cultivo"><input type="radio" name="cultivo" value="${esc(c.codigo)}" ${i === 0 ? "checked" : ""}>
        <div class="nombre"><div class="fila" style="gap:8px"><span class="negrita">${esc(c.descripcion)}</span>${i === 0 ? `<span class="etiqueta">${icono("lightbulb")}Sugerido</span>` : ""}</div>
          <div class="barra-puntaje"><span style="width:${Math.max(0, Math.min(100, c.puntaje || 0))}%"></span></div></div>
        <span class="puntaje">${num(c.puntaje)}</span></label>`).join("")}
      <label class="cultivo"><input type="radio" name="cultivo" value="__otro" ${cultivos.length ? "" : "checked"}><div class="nombre negrita">Otro cultivo</div></label>
      <label class="campo" id="campo-otro" hidden>Nombre del cultivo<input class="input" name="otro" maxlength="100"></label>
      <label class="campo">Observación (opcional)<textarea class="input" name="observacion" maxlength="500"></textarea></label>
      <div id="msg-guardar"></div>
      <button class="btn acento" type="submit">${icono("check_circle")}Guardar registro</button>
    </form>`;

    const form = $res.querySelector("#form-registro"), campoOtro = form.querySelector("#campo-otro");
    const actualizarOtro = () => { campoOtro.hidden = form.cultivo.value !== "__otro"; };
    form.querySelectorAll("input[name=cultivo]").forEach(r => r.addEventListener("change", actualizarOtro));
    actualizarOtro();

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

function tarjetaRegistro(r) {
  const z = r.zona?.descripcion || "Zona no identificada";
  return `<article class="tarjeta plana registro ${r.estado === false ? "anulado" : ""}" data-id="${esc(r.id)}">
    <div class="fila entre"><h3>${esc(r.cultivoDescripcion)}</h3>
      ${r.estado === false ? `<span class="etiqueta gris">Anulado</span>` : r.sugerido ? `<span class="etiqueta verde">Sugerido</span>` : ""}</div>
    <div class="fila muted chico" style="gap:6px">${icono("place")}<span>${esc(z)}</span></div>
    <p class="muted chico">${fecha(r.fechaRegistro)} · ${esc(TIPOS_RIEGO[r.tipoRiego] || r.tipoRiego || "")}${r.puntaje != null ? ` · Aptitud ${num(r.puntaje)}/100` : ""}</p>
    ${r.observacion ? `<p class="chico">${esc(r.observacion)}</p>` : ""}
    <div class="acciones">
      <a class="btn secundario chico" target="_blank" rel="noopener" href="https://www.google.com/maps?q=${r.latitud},${r.longitud}">${icono("map")}Mapa</a>
      ${r.estado === false ? "" : `<button class="btn peligro chico" data-anular>${icono("delete")}Anular</button>`}
    </div></article>`;
}

function vistaRegistros() {
  const st = { pagina: 0, ultima: false };
  $app.innerHTML = `${barra("Mis registros")}
  <div class="pagina"><div id="lista" class="columna"></div><div id="pie"></div></div>`;
  const $lista = $app.querySelector("#lista"), $pie = $app.querySelector("#pie");

  async function cargar() {
    $pie.innerHTML = `<div class="cargando"><span class="spinner"></span>Cargando…</div>`;
    try {
      const d = await api.registros({ page: st.pagina, size: 20 });
      const items = d?.content || [];
      if (st.pagina === 0 && !items.length) {
        $lista.innerHTML = `<div class="vacio">${icono("grass")}<p>Todavía no tienes registros.</p>
          <a class="btn" href="#/nuevo">${icono("add_location_alt")}Nuevo registro</a></div>`;
      } else {
        $lista.insertAdjacentHTML("beforeend", items.map(tarjetaRegistro).join(""));
      }
      st.ultima = d?.last ?? true;
      $pie.innerHTML = st.ultima ? "" : `<button class="btn secundario bloque" id="mas">Cargar más</button>`;
    } catch (e) {
      manejar(e, $pie);
    }
  }

  // El listener va en .pagina (se reemplaza con la vista), no en #app, para no acumularse al navegar
  $app.querySelector(".pagina").addEventListener("click", async ev => {
    if (ev.target.closest("#mas")) { st.pagina++; cargar(); return; }
    const btn = ev.target.closest("[data-anular]");
    if (!btn) return;
    const tarjeta = btn.closest("[data-id]");
    if (!confirm("¿Anular este registro? Seguirá en tu historial como anulado.")) return;
    btn.disabled = true;
    try {
      await api.anularRegistro(tarjeta.dataset.id);
      tarjeta.classList.add("anulado");
      btn.remove();
      tarjeta.querySelector(".fila.entre .etiqueta")?.remove();
      tarjeta.querySelector(".fila.entre").insertAdjacentHTML("beforeend", `<span class="etiqueta gris">Anulado</span>`);
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
  return `<div class="barras">${pares.map(([k, n]) => `<div class="item" title="${esc(k)}: ${n} de ${total}">
    <span class="nombre">${esc(k)}</span><div class="pista"><span style="width:${(n / max) * 100}%"></span></div>
    <span class="num">${n}</span></div>`).join("")}</div>`;
}

async function vistaHistorial() {
  $app.innerHTML = `${barra("Historial")}<div class="pagina" id="cont"><div class="cargando"><span class="spinner"></span>Cargando registros…</div></div>`;
  const $c = $app.querySelector("#cont");
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
    $c.innerHTML = `<div class="vacio">${icono("history")}<p>Aún no hay registros activos para resumir.</p>
      <a class="btn" href="#/nuevo">${icono("add_location_alt")}Nuevo registro</a></div>`;
    return;
  }
  const cultivos = agrupar(activos.map(r => r.cultivoDescripcion || "—"));
  const deptos = agrupar(activos.map(r => r.zona?.departamento || "Sin departamento"));
  const riegos = agrupar(activos.map(r => TIPOS_RIEGO[r.tipoRiego] || r.tipoRiego || "—"));
  const puntajes = activos.map(r => r.puntaje).filter(p => p != null);
  const sugeridos = activos.filter(r => r.sugerido).length;

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
  const tile = (ic, valor, texto) => `<div class="tile">${icono(ic)}<span class="valor">${valor}</span><span class="muted chico">${texto}</span></div>`;

  $c.innerHTML = `
    <div class="tiles">
      ${tile("fact_check", n, "Registros activos")}
      ${tile("eco", distintos, "Cultivos distintos")}
      ${tile("place", deptosDistintos, "Departamentos")}
      ${tile("insights", puntajes.length ? num(puntajes.reduce((a, b) => a + b, 0) / puntajes.length) : "–", "Aptitud promedio")}
    </div>
    <section class="tarjeta columna"><h2>Registros por mes</h2>
      <div class="columnas">${meses.map(m => `<div class="col" title="${m.nombre}: ${m.n}"><div class="alto" data-n="${m.n}" style="height:${(m.n / maxMes) * 100}%"></div>${m.nombre}</div>`).join("")}</div>
    </section>
    <section class="tarjeta columna"><h2>Por cultivo</h2>${barras(cultivos, n)}</section>
    <section class="tarjeta columna"><h2>Por departamento</h2>${barras(deptos, n)}</section>
    <section class="tarjeta columna"><h2>Por tipo de riego</h2>${barras(riegos, n)}
      <p class="muted chico">Elegiste el cultivo sugerido en ${sugeridos} de ${n} registros (${Math.round((sugeridos / n) * 100)}%).</p></section>
    <section class="tarjeta columna"><h2>Últimos registros</h2>
      <ul class="linea-tiempo">${activos.slice(0, 8).map(r => `<li><span class="punto"></span><div>
        <p class="negrita">${esc(r.cultivoDescripcion)}</p>
        <p class="muted chico">${fecha(r.fechaRegistro)} · ${esc(r.zona?.descripcion || "Zona no identificada")}</p></div></li>`).join("")}</ul>
    </section>`;
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

async function vistaClima() {
  $app.innerHTML = `${barra("Clima", { derecha: `<button class="icono-btn" id="recargar" aria-label="Actualizar">${icono("refresh")}</button>` })}
    <div class="pagina" id="cont"></div>`;
  const $c = $app.querySelector("#cont");
  $app.querySelector("#recargar").addEventListener("click", cargar);

  async function cargar() {
    $c.innerHTML = `<div class="cargando"><span class="spinner"></span>Obteniendo tu ubicación…</div>`;
    let p;
    try { p = await ubicacion(); } catch (e) { $c.innerHTML = aviso("error", esc(e.message)); return; }
    $c.innerHTML = `<div class="cargando"><span class="spinner"></span>Consultando el pronóstico…</div>`;
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
    $c.innerHTML = `
      <section class="tarjeta clima-actual">
        <div class="fila entre"><div><p class="muted chico">Ahora</p><p class="temp">${num(a.temperature_2m)}°</p>
          <p class="negrita">${desc}</p><p class="muted chico">Sensación ${num(a.apparent_temperature)}°</p></div>
          ${icono(ic, "grande")}</div>
        <div class="datos">
          <div><span class="muted">Humedad</span><strong>${num(a.relative_humidity_2m)}%</strong></div>
          <div><span class="muted">Lluvia</span><strong>${num(a.precipitation, 1)} mm</strong></div>
          <div><span class="muted">Viento</span><strong>${num(a.wind_speed_10m)} km/h</strong></div>
        </div>
      </section>
      <section class="tarjeta"><h2 style="margin-bottom:4px">Próximos 7 días</h2>
        ${dl.time.map((t, i) => {
      const f = new Date(`${t}T12:00:00`), [dd, di] = tiempo(dl.weather_code[i]);
      const mn = dl.temperature_2m_min[i], mx = dl.temperature_2m_max[i];
      return `<div class="dia" title="${dd}">
            <span class="negrita">${i === 0 ? "Hoy" : DIAS[f.getDay()]}</span>${icono(di)}
            <div class="rango"><span class="muted">${num(mn)}°</span><div class="pista"><span style="left:${((mn - minS) / rango) * 100}%;right:${100 - ((mx - minS) / rango) * 100}%"></span></div><span>${num(mx)}°</span></div>
            <span class="lluvia">${icono("water_drop")}${num(dl.precipitation_probability_max[i])}%</span></div>`;
    }).join("")}
      </section>
      <p class="muted chico">Pronóstico de Open-Meteo para ${p.latitud.toFixed(3)}, ${p.longitud.toFixed(3)} (${esc(d.timezone || "")}).</p>`;
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
