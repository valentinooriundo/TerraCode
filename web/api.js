// Cliente del API de TerraCodex (mismo dominio: /api/...). Guarda la sesión en el navegador y renueva el access
// token con el refresh token cuando el API responde 401.

const CLAVE_SESION = "terracode.sesion";
const CLAVE_GOOGLE = "terracode.google";
const VIGENCIA_GOOGLE_MS = 10 * 60 * 1000;

export class ApiError extends Error {
  constructor(status, message, errors) {
    super(message || "No se pudo completar la operación.");
    this.status = status;
    this.errors = errors || null;
  }
}
export class SesionExpirada extends ApiError {
  constructor() { super(401, "Tu sesión venció. Vuelve a iniciar sesión."); }
}

function leer(almacen, clave) {
  try { return JSON.parse(almacen.getItem(clave)); } catch { return null; }
}
function escribir(almacen, clave, valor) {
  try {
    if (valor == null) almacen.removeItem(clave); else almacen.setItem(clave, JSON.stringify(valor));
  } catch { /* almacenamiento bloqueado: la sesión dura lo que la pestaña */ }
}

let sesionMemoria = leer(localStorage, CLAVE_SESION);

export function sesion() { return sesionMemoria; }
function guardarSesion(datos) {
  sesionMemoria = datos ? {
    accessToken: datos.accessToken,
    refreshToken: datos.refreshToken,
    usuario: datos.usuario,
  } : null;
  escribir(localStorage, CLAVE_SESION, sesionMemoria);
}

async function llamar(metodo, ruta, cuerpo, { token, timeout = 30000 } = {}) {
  const ctrl = new AbortController();
  const reloj = setTimeout(() => ctrl.abort(), timeout);
  const headers = { Accept: "application/json" };
  if (cuerpo !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  let res;
  try {
    res = await fetch(ruta, {
      method: metodo, headers, signal: ctrl.signal,
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    });
  } catch (e) {
    throw new ApiError(0, e.name === "AbortError"
      ? "El servidor tardó demasiado en responder. Inténtalo de nuevo."
      : "No hay conexión con el servidor. Revisa tu internet.");
  } finally {
    clearTimeout(reloj);
  }
  let json = null;
  try { json = await res.json(); } catch { /* sin cuerpo */ }
  return { status: res.status, ok: res.ok && (json?.ok ?? true), json };
}

function error(r) {
  const msg = r.json?.message || (r.status >= 500 ? "El servidor tuvo un problema. Inténtalo más tarde." : null);
  return new ApiError(r.status, msg, r.json?.errors);
}

let renovando = null;
async function renovar() {
  const actual = sesionMemoria;
  if (!actual?.refreshToken) return false;
  renovando ??= (async () => {
    const r = await llamar("POST", "/api/auth/refresh", { refreshToken: actual.refreshToken });
    if (r.ok && r.json?.data?.accessToken) { guardarSesion(r.json.data); return true; }
    if (r.status === 0) throw error(r);
    guardarSesion(null);
    return false;
  })().finally(() => { renovando = null; });
  return renovando;
}

/** Llamada autenticada; si el token venció lo renueva una vez y reintenta. */
export async function api(metodo, ruta, cuerpo, opciones = {}) {
  if (!sesionMemoria) throw new SesionExpirada();
  let r = await llamar(metodo, ruta, cuerpo, { ...opciones, token: sesionMemoria.accessToken });
  if (r.status === 401) {
    if (!(await renovar())) throw new SesionExpirada();
    r = await llamar(metodo, ruta, cuerpo, { ...opciones, token: sesionMemoria.accessToken });
    if (r.status === 401) { guardarSesion(null); throw new SesionExpirada(); }
  }
  if (!r.ok) throw error(r);
  return r.json?.data;
}

export async function login(usuario, contrasena) {
  const r = await llamar("POST", "/api/auth/login", { login: usuario, contrasena, canal: "WEB" });
  if (!r.ok) {
    if (r.status === 401) throw new ApiError(401, "Usuario o contraseña incorrectos.");
    throw error(r);
  }
  guardarSesion(r.json.data);
  return r.json.data.usuario;
}

export async function logout() {
  const actual = sesionMemoria;
  guardarSesion(null);
  if (actual?.refreshToken) {
    try { await llamar("POST", "/api/auth/logout", { refreshToken: actual.refreshToken }, { timeout: 5000 }); } catch { }
  }
}

// --- Google -------------------------------------------------------------------------------------------------------
// La app genera un verificador secreto y solo envía su SHA-256. Guarda id + verificador en esta pestaña, va a Google
// y el backend la devuelve a /app/?google=ok|error, donde se canjea por la sesión.

function verificadorNuevo() {
  const bytes = crypto.getRandomValues(new Uint8Array(48));
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
async function sha256Hex(texto) {
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(texto));
  return [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2, "0")).join("");
}

export async function iniciarGoogle() {
  const verificador = verificadorNuevo();
  const desafio = await sha256Hex(verificador);
  const r = await llamar("POST", "/api/auth/google/inicio", { canal: "WEB", desafio });
  if (!r.ok || !r.json?.data?.url) {
    if (r.status === 503 || r.status === 404) throw new ApiError(r.status, "El inicio con Google no está disponible ahora.");
    throw error(r);
  }
  escribir(sessionStorage, CLAVE_GOOGLE, { id: r.json.data.id, verificador, ts: Date.now() });
  location.href = r.json.data.url;
}

/** Al volver de Google: canjea el intento guardado. Devuelve el usuario, o lanza ApiError con el motivo. */
export async function retomarGoogle(resultado) {
  const intento = leer(sessionStorage, CLAVE_GOOGLE);
  escribir(sessionStorage, CLAVE_GOOGLE, null);
  if (resultado === "error") throw new ApiError(401, "Google no autorizó el inicio de sesión. Inténtalo de nuevo.");
  if (!intento?.id || Date.now() - intento.ts > VIGENCIA_GOOGLE_MS) {
    throw new ApiError(401, "El inicio de sesión con Google venció o se abrió en otra pestaña. Inténtalo de nuevo.");
  }
  for (let i = 0; i < 5; i++) {
    const r = await llamar("POST", "/api/auth/google/sesion", { id: intento.id, verificador: intento.verificador });
    if (r.status === 200 && r.json?.data?.accessToken) { guardarSesion(r.json.data); return r.json.data.usuario; }
    if (r.status !== 202) {
      if (r.status === 403) throw new ApiError(403, r.json?.message || "Tu cuenta no tiene acceso a la versión web.");
      if (r.status === 401) throw new ApiError(401, "El inicio de sesión con Google no es válido o ya se usó. Inténtalo de nuevo.");
      throw error(r);
    }
    await new Promise(ok => setTimeout(ok, 2000));
  }
  throw new ApiError(408, "Google no terminó de confirmar el inicio de sesión. Inténtalo de nuevo.");
}

// --- Campo ---------------------------------------------------------------------------------------------------------

export const recomendaciones = (latitud, longitud, tipoRiego) =>
  // La primera consulta de un punto descarga el clima histórico: puede tardar hasta ~100 s
  api("POST", "/api/campo/recomendaciones", { latitud, longitud, tipoRiego }, { timeout: 150000 });

export const guardarRegistro = datos => api("POST", "/api/campo/registros", datos);

export function registros({ page = 0, size = 20, estado } = {}) {
  const q = new URLSearchParams({ page, size, sort: "fechaRegistro,desc" });
  if (estado) q.set("estado", estado);
  return api("GET", `/api/campo/registros?${q}`);
}

export const anularRegistro = id => api("DELETE", `/api/campo/registros/${encodeURIComponent(id)}`);
