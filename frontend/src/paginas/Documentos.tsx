import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { api, ErrorApi } from "../api/cliente";
import type { Documento } from "../api/tipos";

const EXTENSIONES = [".pdf", ".txt", ".md", ".docx", ".csv"];
const MAXIMO_MB = 10;

type EstadoSubida =
  | { tipo: "inactivo" }
  | { tipo: "procesando"; nombre: string }
  | { tipo: "ok"; mensaje: string }
  | { tipo: "error"; mensaje: string };

export default function Documentos() {
  const [documentos, setDocumentos] = useState<Documento[] | null>(null);
  const [errorLista, setErrorLista] = useState("");
  const [visibilidad, setVisibilidad] = useState<"publico" | "interno">("publico");
  const [subida, setSubida] = useState<EstadoSubida>({ tipo: "inactivo" });
  const [arrastrando, setArrastrando] = useState(false);
  const entradaRef = useRef<HTMLInputElement>(null);

  const cargar = useCallback(async () => {
    try {
      setDocumentos(await api.documentos());
      setErrorLista("");
    } catch (e) {
      setErrorLista(e instanceof ErrorApi ? e.message : "No se pudieron cargar los documentos.");
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function subir(archivo: File) {
    // Validación previa en el navegador (el backend vuelve a validar todo).
    const extension = archivo.name.slice(archivo.name.lastIndexOf(".")).toLowerCase();
    if (!EXTENSIONES.includes(extension)) {
      setSubida({ tipo: "error", mensaje: `Formato no permitido. Se aceptan: ${EXTENSIONES.join(", ")}.` });
      return;
    }
    if (archivo.size > MAXIMO_MB * 1024 * 1024) {
      setSubida({ tipo: "error", mensaje: `El archivo pasa del máximo de ${MAXIMO_MB} MB.` });
      return;
    }
    setSubida({ tipo: "procesando", nombre: archivo.name });
    try {
      const r = await api.subirDocumento(archivo, visibilidad);
      setSubida({ tipo: "ok", mensaje: r.mensaje });
      cargar();
    } catch (e) {
      setSubida({ tipo: "error", mensaje: e instanceof ErrorApi ? e.message : "No se pudo subir el archivo." });
    }
  }

  function alSoltar(evento: DragEvent<HTMLDivElement>) {
    evento.preventDefault();
    setArrastrando(false);
    const archivo = evento.dataTransfer.files[0];
    if (archivo) subir(archivo);
  }

  async function borrar(doc: Documento) {
    if (!window.confirm(`¿Borrar «${doc.titulo}» y sus ${doc.fragmentos} fragmentos de la base de conocimiento?`)) return;
    try {
      await api.borrarDocumento(doc.id);
      setSubida({ tipo: "ok", mensaje: `«${doc.titulo}» se borró de la base de conocimiento.` });
      cargar();
    } catch (e) {
      setSubida({ tipo: "error", mensaje: e instanceof ErrorApi ? e.message : "No se pudo borrar." });
    }
  }

  const procesando = subida.tipo === "procesando";
  const totalFragmentos = documentos?.reduce((s, d) => s + d.fragmentos, 0) ?? 0;

  return (
    <div className="pagina-documentos">
      <h2>Base de conocimiento</h2>
      <p className="ayuda">
        Patroclo solo responde con lo que hay aquí. Sube un documento y en unos segundos podrá usarlo para responder.
      </p>

      <div
        className={`zona-carga ${arrastrando ? "arrastrando" : ""} ${procesando ? "deshabilitada" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setArrastrando(true);
        }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={procesando ? (e) => e.preventDefault() : alSoltar}
        onClick={() => !procesando && entradaRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && !procesando && entradaRef.current?.click()}
      >
        {procesando ? (
          <>
            <span className="puntos" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <strong>Procesando «{subida.nombre}»…</strong>
            <small>Extrayendo el texto, fragmentando y calculando los embeddings.</small>
          </>
        ) : (
          <>
            <strong>Arrastra un archivo aquí o haz clic para elegirlo</strong>
            <small>
              {EXTENSIONES.join(" · ")} — máximo {MAXIMO_MB} MB
            </small>
          </>
        )}
        <input
          ref={entradaRef}
          type="file"
          accept={EXTENSIONES.join(",")}
          hidden
          onChange={(e) => {
            const archivo = e.target.files?.[0];
            if (archivo) subir(archivo);
            e.target.value = ""; // permite volver a elegir el mismo archivo
          }}
        />
      </div>

      <div className="opciones-carga">
        <label>
          Visibilidad:{" "}
          <select value={visibilidad} onChange={(e) => setVisibilidad(e.target.value as "publico" | "interno")} disabled={procesando}>
            <option value="publico">Pública (la podrá usar el futuro asistente de WhatsApp)</option>
            <option value="interno">Interna (solo el equipo)</option>
          </select>
        </label>
      </div>

      {subida.tipo === "ok" && <div className="aviso aviso-ok">{subida.mensaje}</div>}
      {subida.tipo === "error" && (
        <div className="aviso aviso-error" role="alert">
          {subida.mensaje}
        </div>
      )}

      {errorLista && <div className="aviso aviso-error">{errorLista}</div>}
      {documentos && (
        <>
          <p className="resumen-documentos">
            {documentos.length} documentos · {totalFragmentos} fragmentos indexados
          </p>
          <div className="tabla-envoltura">
            <table className="tabla-documentos">
              <thead>
                <tr>
                  <th>Documento</th>
                  <th>Tipo</th>
                  <th>Fragmentos</th>
                  <th>Visibilidad</th>
                  <th>Subido por</th>
                  <th aria-label="Acciones" />
                </tr>
              </thead>
              <tbody>
                {documentos.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <div className="doc-titulo">{d.titulo}</div>
                      <div className="doc-archivo">
                        {d.nombre_original} · {formatoTamano(d.tamano_bytes)}
                      </div>
                    </td>
                    <td>
                      <span className="insignia">{d.tipo.toUpperCase()}</span>
                    </td>
                    <td>{d.fragmentos}</td>
                    <td>
                      <span className={`insignia insignia-${d.visibilidad}`}>{d.visibilidad === "publico" ? "pública" : "interna"}</span>
                    </td>
                    <td>{d.subido_por}</td>
                    <td>
                      {d.puede_borrar && (
                        <button className="boton boton-peligro" onClick={() => borrar(d)}>
                          Borrar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function formatoTamano(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
