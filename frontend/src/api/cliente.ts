// Cliente de la API: un solo lugar que sabe la URL, pone el token y traduce errores.
import type {
  ConversacionCompleta,
  Documento,
  EstadoSalud,
  RespuestaChat,
  RespuestaSesion,
  RespuestaSubida,
  ResumenConversacion,
  Usuario,
} from "./tipos";

export const URL_API = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** Error con un mensaje apto para mostrarle al usuario. */
export class ErrorApi extends Error {
  constructor(
    message: string,
    public estado: number, // 0 = no hubo respuesta (red caída, servidor apagado)
  ) {
    super(message);
  }
}

let token: string | null = null;
let alExpirar: (() => void) | null = null;

export function usarToken(nuevo: string | null) {
  token = nuevo;
}

/** Qué hacer si la API dice 401 (sesión vencida o revocada): lo define la sesión. */
export function alExpirarSesion(funcion: () => void) {
  alExpirar = funcion;
}

async function pedir<T>(ruta: string, opciones: RequestInit = {}, conToken = true): Promise<T> {
  const cabeceras = new Headers(opciones.headers);
  // ngrok (despliegue, paso 7) muestra una página de aviso a los navegadores; esta
  // cabecera la salta. En local no hace nada.
  cabeceras.set("ngrok-skip-browser-warning", "1");
  if (conToken && token) cabeceras.set("Authorization", `Bearer ${token}`);
  if (opciones.body && !(opciones.body instanceof FormData)) cabeceras.set("Content-Type", "application/json");

  let respuesta: Response;
  try {
    respuesta = await fetch(`${URL_API}${ruta}`, { ...opciones, headers: cabeceras });
  } catch {
    throw new ErrorApi("No se pudo conectar con el servidor. Revisa que el backend esté encendido.", 0);
  }

  if (respuesta.status === 401 && conToken) {
    alExpirar?.();
    throw new ErrorApi("Tu sesión expiró. Vuelve a ingresar.", 401);
  }
  if (respuesta.status === 204) return undefined as T;

  const cuerpo = await respuesta.json().catch(() => null);
  if (!respuesta.ok) throw new ErrorApi(mensajeDeError(cuerpo, respuesta.status), respuesta.status);
  return cuerpo as T;
}

function mensajeDeError(cuerpo: unknown, estado: number): string {
  const c = cuerpo as { detail?: unknown; detalle?: string } | null;
  if (c?.detalle) return c.detalle; // errores propios (503 del modelo o de la base, 500 con id)
  if (typeof c?.detail === "string") return c.detail; // HTTPException
  if (Array.isArray(c?.detail)) {
    // 422 de validación de pydantic: se muestra el primer problema.
    const primero = c.detail[0] as { msg?: string } | undefined;
    return primero?.msg?.replace(/^Value error, /, "") ?? "Datos inválidos.";
  }
  if (estado >= 500) return "El servidor tuvo un problema. Intenta de nuevo.";
  return `Error ${estado}.`;
}

export const api = {
  salud: () => pedir<EstadoSalud>("/health", {}, false),

  registro: (correo: string, nombre: string, contrasena: string) =>
    pedir<RespuestaSesion>("/api/auth/registro", { method: "POST", body: JSON.stringify({ correo, nombre, contrasena }) }, false),
  ingresar: (correo: string, contrasena: string) =>
    pedir<RespuestaSesion>("/api/auth/ingresar", { method: "POST", body: JSON.stringify({ correo, contrasena }) }, false),
  yo: () => pedir<Usuario>("/api/auth/yo"),
  salir: () => pedir<void>("/api/auth/salir", { method: "POST" }),

  preguntar: (pregunta: string, conversacion_id?: string) =>
    pedir<RespuestaChat>("/api/chat", { method: "POST", body: JSON.stringify({ pregunta, conversacion_id }) }),
  conversaciones: () => pedir<ResumenConversacion[]>("/api/conversaciones"),
  conversacion: (id: string) => pedir<ConversacionCompleta>(`/api/conversaciones/${id}`),
  borrarConversacion: (id: string) => pedir<void>(`/api/conversaciones/${id}`, { method: "DELETE" }),

  documentos: () => pedir<Documento[]>("/api/documentos"),
  subirDocumento: (archivo: File, visibilidad: "publico" | "interno") => {
    const datos = new FormData();
    datos.append("archivo", archivo);
    datos.append("visibilidad", visibilidad);
    return pedir<RespuestaSubida>("/api/documentos", { method: "POST", body: datos });
  },
  borrarDocumento: (id: string) => pedir<void>(`/api/documentos/${id}`, { method: "DELETE" }),
};
