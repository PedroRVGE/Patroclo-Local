import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type SyntheticEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ErrorApi } from "../api/cliente";
import type { Fuente, Paso, ResumenConversacion } from "../api/tipos";
import MensajeAsistente from "../componentes/MensajeAsistente";

interface MensajeVista {
  clave: string;
  rol: "usuario" | "asistente" | "error";
  contenido: string;
  fuentes?: Fuente[];
  pasos?: Paso[];
  rechazada?: boolean;
  tiempoMs?: number | null;
}

const SUGERENCIAS = [
  "¿Qué quesos vende Del Pastor?",
  "¿El queso de cabra tiene lactosa?",
  "¿Por qué el ibérico antes se llamaba Manchego?",
  "Dame una receta con queso crema de cabra",
];

export default function Chat() {
  const { id } = useParams();
  const navegar = useNavigate();
  const [conversaciones, setConversaciones] = useState<ResumenConversacion[]>([]);
  const [mensajes, setMensajes] = useState<MensajeVista[]>([]);
  const [texto, setTexto] = useState("");
  const [pensando, setPensando] = useState(false);
  const [segundos, setSegundos] = useState(0);
  const [cargandoConversacion, setCargandoConversacion] = useState(false);
  const [errorLista, setErrorLista] = useState("");
  const [panelAbierto, setPanelAbierto] = useState(false); // solo en pantallas pequeñas
  const cargadaRef = useRef<string | undefined>(undefined); // conversación que ya está en pantalla
  const finRef = useRef<HTMLDivElement>(null);
  const entradaRef = useRef<HTMLTextAreaElement>(null);

  const cargarLista = useCallback(async () => {
    try {
      setConversaciones(await api.conversaciones());
      setErrorLista("");
    } catch (e) {
      setErrorLista(e instanceof ErrorApi ? e.message : "No se pudo cargar el historial.");
    }
  }, []);

  useEffect(() => {
    cargarLista();
  }, [cargarLista]);

  // Abrir una conversación del historial (o limpiar al pulsar «Nueva conversación»).
  useEffect(() => {
    setPanelAbierto(false);
    if (id === cargadaRef.current) return; // ya está en pantalla (p. ej. recién creada)
    cargadaRef.current = id;
    if (!id) {
      setMensajes([]);
      return;
    }
    setCargandoConversacion(true);
    api
      .conversacion(id)
      .then((c) =>
        setMensajes(
          c.mensajes.map((m) => ({
            clave: m.id,
            rol: m.rol,
            contenido: m.contenido,
            fuentes: m.fuentes,
            pasos: m.pasos,
            rechazada: m.rechazada,
            tiempoMs: m.tiempo_ms,
          })),
        ),
      )
      .catch((e) => {
        setMensajes([{ clave: "error", rol: "error", contenido: e instanceof ErrorApi ? e.message : "No se pudo abrir la conversación." }]);
      })
      .finally(() => setCargandoConversacion(false));
  }, [id]);

  // Contador de segundos mientras el modelo local trabaja.
  useEffect(() => {
    if (!pensando) return;
    setSegundos(0);
    const intervalo = setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => clearInterval(intervalo);
  }, [pensando]);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [mensajes, pensando]);

  async function enviar(pregunta: string) {
    pregunta = pregunta.trim();
    if (!pregunta || pensando) return;
    setTexto("");
    setMensajes((m) => [...m, { clave: `u-${Date.now()}`, rol: "usuario", contenido: pregunta }]);
    setPensando(true);
    try {
      const r = await api.preguntar(pregunta, id);
      setMensajes((m) => [
        ...m,
        { clave: `a-${Date.now()}`, rol: "asistente", contenido: r.respuesta, fuentes: r.fuentes, pasos: r.pasos, rechazada: r.rechazada, tiempoMs: r.tiempo_ms },
      ]);
      if (r.conversacion_id !== id) {
        cargadaRef.current = r.conversacion_id;
        navegar(`/chat/${r.conversacion_id}`, { replace: true });
      }
      cargarLista();
    } catch (e) {
      setMensajes((m) => [...m, { clave: `e-${Date.now()}`, rol: "error", contenido: e instanceof ErrorApi ? e.message : "Ocurrió un error inesperado." }]);
      setTexto(pregunta); // para poder reintentar sin volver a escribir
    } finally {
      setPensando(false);
      entradaRef.current?.focus();
    }
  }

  function alEnviar(evento: SyntheticEvent) {
    evento.preventDefault();
    enviar(texto);
  }

  function alTeclear(evento: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter envía; Shift+Enter hace un salto de línea.
    if (evento.key === "Enter" && !evento.shiftKey) {
      evento.preventDefault();
      enviar(texto);
    }
  }

  async function borrarConversacion(c: ResumenConversacion) {
    if (!window.confirm(`¿Borrar la conversación «${c.titulo}»?`)) return;
    try {
      await api.borrarConversacion(c.id);
      if (c.id === id) navegar("/");
      cargarLista();
    } catch (e) {
      setErrorLista(e instanceof ErrorApi ? e.message : "No se pudo borrar.");
    }
  }

  return (
    <div className="chat">
      <aside className={`panel-conversaciones ${panelAbierto ? "abierto" : ""}`}>
        <button className="boton boton-principal boton-ancho" onClick={() => navegar("/")}>
          + Nueva conversación
        </button>
        {errorLista && <div className="aviso aviso-error">{errorLista}</div>}
        <ul className="lista-conversaciones">
          {conversaciones.map((c) => (
            <li key={c.id} className={c.id === id ? "activa" : ""}>
              <button className="conversacion-titulo" onClick={() => navegar(`/chat/${c.id}`)} title={c.titulo}>
                {c.titulo}
              </button>
              <button className="conversacion-borrar" onClick={() => borrarConversacion(c)} aria-label={`Borrar «${c.titulo}»`} title="Borrar">
                ×
              </button>
            </li>
          ))}
          {!conversaciones.length && !errorLista && <li className="lista-vacia">Aún no tienes conversaciones.</li>}
        </ul>
      </aside>

      <section className="zona-chat">
        <button className="boton boton-secundario boton-historial" onClick={() => setPanelAbierto((a) => !a)}>
          {panelAbierto ? "Cerrar historial" : "Historial"}
        </button>

        <div className="mensajes" aria-live="polite">
          {cargandoConversacion && <div className="cargando-pagina">Abriendo la conversación…</div>}
          {!cargandoConversacion && mensajes.length === 0 && (
            <div className="bienvenida">
              <img src="/queso.svg" alt="" width={64} height={64} />
              <h2>¿Qué quieres saber de los quesos de cabra?</h2>
              <p>
                Respondo solo con la base de conocimiento de Del Pastor y te muestro de dónde saco cada dato. Si no lo sé, te lo
                digo.
              </p>
              <div className="sugerencias">
                {SUGERENCIAS.map((s) => (
                  <button key={s} className="sugerencia" onClick={() => enviar(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {mensajes.map((m) =>
            m.rol === "asistente" ? (
              <MensajeAsistente key={m.clave} contenido={m.contenido} fuentes={m.fuentes ?? []} pasos={m.pasos ?? []} rechazada={!!m.rechazada} tiempoMs={m.tiempoMs ?? null} />
            ) : (
              <div key={m.clave} className={`mensaje mensaje-${m.rol}`} role={m.rol === "error" ? "alert" : undefined}>
                {m.contenido}
              </div>
            ),
          )}
          {pensando && (
            <div className="mensaje mensaje-asistente pensando">
              <span className="puntos" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
              Patroclo está pensando… {segundos} s
              {segundos >= 5 && <small> (el modelo corre en un PC local; tarda unos segundos)</small>}
            </div>
          )}
          <div ref={finRef} />
        </div>

        <form className="entrada" onSubmit={alEnviar}>
          <textarea
            ref={entradaRef}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={alTeclear}
            placeholder="Pregunta sobre quesos, leche de cabra, recetas…"
            rows={2}
            maxLength={1000}
            disabled={pensando}
            aria-label="Tu pregunta"
          />
          <button type="submit" className="boton boton-principal" disabled={pensando || !texto.trim()}>
            Enviar
          </button>
        </form>
      </section>
    </div>
  );
}
