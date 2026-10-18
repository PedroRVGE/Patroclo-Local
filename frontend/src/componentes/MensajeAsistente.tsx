// Una respuesta de Patroclo: el texto, sus fuentes (con el fragmento usado) y el recorrido
// por el grafo de LangGraph.
import { useRef, useState } from "react";
import type { Fuente, Paso } from "../api/tipos";
import TextoRespuesta from "./TextoRespuesta";

interface Props {
  contenido: string;
  fuentes: Fuente[];
  pasos: Paso[];
  rechazada: boolean;
  tiempoMs: number | null;
}

const NOMBRES_NODO: Record<string, string> = {
  reformular_pregunta: "Reformular la pregunta",
  clasificar_intencion: "Clasificar la intención",
  recuperar_contexto: "Buscar en la base vectorial",
  evaluar_contexto: "Juez: ¿el contexto alcanza?",
  generar_respuesta: "Generar la respuesta",
  rechazar: "Rechazar",
  responder_saludo: "Saludar",
  guardar_historial: "Guardar en el historial",
};

export default function MensajeAsistente({ contenido, fuentes, pasos, rechazada, tiempoMs }: Props) {
  const [fuentesAbiertas, setFuentesAbiertas] = useState(false);
  const [resaltada, setResaltada] = useState<number | null>(null);
  const refFuentes = useRef<HTMLDivElement>(null);

  function verFuente(numero: number) {
    setFuentesAbiertas(true);
    setResaltada(numero);
    requestAnimationFrame(() =>
      refFuentes.current?.querySelector(`[data-fuente="${numero}"]`)?.scrollIntoView({ behavior: "smooth", block: "nearest" }),
    );
  }

  return (
    <div className={`mensaje mensaje-asistente ${rechazada ? "mensaje-rechazado" : ""}`}>
      {rechazada && <div className="etiqueta-rechazo">Sin información suficiente</div>}
      <TextoRespuesta texto={contenido} totalFuentes={fuentes.length} alCitar={verFuente} />

      {fuentes.length > 0 && (
        <details className="desplegable" open={fuentesAbiertas} onToggle={(e) => setFuentesAbiertas(e.currentTarget.open)}>
          <summary>Fuentes ({fuentes.length})</summary>
          <div className="fuentes" ref={refFuentes}>
            {fuentes.map((f) => (
              <div key={f.numero} data-fuente={f.numero} className={`fuente ${resaltada === f.numero ? "fuente-resaltada" : ""}`}>
                <div className="fuente-cabecera">
                  <span className="fuente-numero">{f.numero}</span>
                  <span className="fuente-documento">{f.documento ?? f.archivo ?? "Documento"}</span>
                  <span className="fuente-similitud" title="Similitud con la pregunta (1 − distancia coseno)">
                    {Math.round(f.similitud * 100)} %
                  </span>
                </div>
                {(f.seccion || f.pagina) && (
                  <div className="fuente-ubicacion">
                    {f.seccion && <>Sección: {f.seccion}</>}
                    {f.seccion && f.pagina ? " · " : ""}
                    {f.pagina ? <>Página {f.pagina}</> : null}
                  </div>
                )}
                <blockquote className="fuente-fragmento">{sinLineaDeContexto(f.fragmento)}</blockquote>
              </div>
            ))}
          </div>
        </details>
      )}

      {pasos.length > 0 && (
        <details className="desplegable">
          <summary>
            Recorrido por el grafo{tiempoMs != null && <> · {(tiempoMs / 1000).toFixed(1)} s</>}
          </summary>
          <ol className="pasos">
            {pasos.map((p, i) => (
              <li key={i} className={`paso paso-${p.nodo}`}>
                <div className="paso-cabecera">
                  <span className="paso-nombre">{NOMBRES_NODO[p.nodo] ?? p.nodo}</span>
                  <code className="paso-nodo">{p.nodo}</code>
                  <span className="paso-ms">{p.ms >= 1000 ? `${(p.ms / 1000).toFixed(1)} s` : `${p.ms} ms`}</span>
                </div>
                {p.detalle && <div className="paso-detalle">{p.detalle}</div>}
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}

/** Los fragmentos empiezan con «Documento: … | Sección: …» (contexto para el modelo); aquí ya se muestra arriba. */
function sinLineaDeContexto(texto: string): string {
  return texto.replace(/^Documento: .*\n\n/, "");
}
