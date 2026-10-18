// Tipos que devuelve la API (espejo de los modelos de pydantic del backend).

export interface Usuario {
  id: string;
  correo: string;
  nombre: string;
  creado_en?: string | null;
}

export interface RespuestaSesion {
  token: string;
  tipo: string;
  expira_en: string;
  usuario: Usuario;
}

export interface Fuente {
  numero: number;
  documento: string | null;
  archivo?: string | null;
  documento_id?: string | null;
  pagina?: number | null;
  seccion?: string | null;
  fragmento: string;
  similitud: number;
}

export interface Paso {
  nodo: string;
  detalle: string;
  ms: number;
}

export interface RespuestaChat {
  respuesta: string;
  conversacion_id: string;
  fuentes: Fuente[];
  pasos: Paso[];
  rechazada: boolean;
  tiempo_ms: number;
  con_historial: boolean;
}

export interface ResumenConversacion {
  id: string;
  titulo: string;
  creada_en: string | null;
  actualizada_en: string | null;
  mensajes: number;
}

export interface Mensaje {
  id: string;
  rol: "usuario" | "asistente";
  contenido: string;
  fuentes: Fuente[];
  pasos: Paso[];
  rechazada: boolean;
  tiempo_ms: number | null;
  creado_en: string | null;
}

export interface ConversacionCompleta {
  id: string;
  titulo: string;
  creada_en: string | null;
  mensajes: Mensaje[];
}

export interface Documento {
  id: string;
  titulo: string;
  nombre_original: string;
  tipo: string;
  tamano_bytes: number;
  fragmentos: number;
  visibilidad: "publico" | "interno";
  subido_en: string | null;
  subido_por: string;
  puede_borrar: boolean;
}

export interface RespuestaSubida {
  documento: Documento;
  nuevo: boolean;
  mensaje: string;
}

export interface EstadoSalud {
  estado: "ok" | "degradado";
  base_datos: { estado: string };
  modelo_local: { estado: string; chat?: { modelo: string; instalado: boolean } };
}
