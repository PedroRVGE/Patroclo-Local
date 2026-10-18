// Muestra la respuesta del modelo con un Markdown mínimo: **negrita**, listas y citas [n].
//
// Construye elementos de React; nunca usa dangerouslySetInnerHTML. Así, aunque el modelo
// (o un documento cargado) devuelva HTML o <script>, se muestra como texto y no se ejecuta.
import type { ReactNode } from "react";

interface Props {
  texto: string;
  totalFuentes: number;
  alCitar?: (numero: number) => void;
}

const PATRON_EN_LINEA = /(\*\*[^*]+\*\*|\[\d+\])/g;

export default function TextoRespuesta({ texto, totalFuentes, alCitar }: Props) {
  const bloques: ReactNode[] = [];
  let lista: { ordenada: boolean; items: string[] } | null = null;

  const cerrarLista = () => {
    if (!lista) return;
    const items = lista.items.map((item, i) => <li key={i}>{enLinea(item, totalFuentes, alCitar)}</li>);
    bloques.push(lista.ordenada ? <ol key={bloques.length}>{items}</ol> : <ul key={bloques.length}>{items}</ul>);
    lista = null;
  };

  for (const lineaCruda of texto.split("\n")) {
    const linea = lineaCruda.trim();
    const vineta = linea.match(/^[*-]\s+(.*)/);
    const numerada = linea.match(/^\d+[.)]\s+(.*)/);
    if (vineta || numerada) {
      const ordenada = Boolean(numerada);
      if (lista && lista.ordenada !== ordenada) cerrarLista();
      lista ??= { ordenada, items: [] };
      lista.items.push((vineta ?? numerada)![1]);
      continue;
    }
    cerrarLista();
    if (!linea) continue;
    const titulo = linea.match(/^#{1,4}\s+(.*)/);
    bloques.push(
      titulo ? (
        <p key={bloques.length} className="respuesta-titulo">
          {enLinea(titulo[1], totalFuentes, alCitar)}
        </p>
      ) : (
        <p key={bloques.length}>{enLinea(linea, totalFuentes, alCitar)}</p>
      ),
    );
  }
  cerrarLista();
  return <div className="texto-respuesta">{bloques}</div>;
}

function enLinea(texto: string, totalFuentes: number, alCitar?: (n: number) => void): ReactNode[] {
  return texto.split(PATRON_EN_LINEA).map((parte, i) => {
    if (parte.startsWith("**") && parte.endsWith("**")) return <strong key={i}>{parte.slice(2, -2)}</strong>;
    const cita = parte.match(/^\[(\d+)\]$/);
    if (cita) {
      const n = Number(cita[1]);
      // Una cita a una fuente que no existe se muestra como texto (no se inventa el vínculo).
      if (n < 1 || n > totalFuentes) return parte;
      return (
        <button key={i} type="button" className="cita" title={`Ver la fuente ${n}`} onClick={() => alCitar?.(n)}>
          {n}
        </button>
      );
    }
    return parte;
  });
}
