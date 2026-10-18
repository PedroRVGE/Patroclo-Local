// Consulta /health cada 30 s y avisa si el backend, la base o el modelo local no están
// disponibles (PDF §2.3: «mostrar mensajes de error cuando el agente no pueda responder»).
import { useEffect, useState } from "react";
import { api } from "../api/cliente";

type Estado = "ok" | "sin-backend" | "sin-modelo" | "sin-base";

export default function AvisoServicio() {
  const [estado, setEstado] = useState<Estado>("ok");

  useEffect(() => {
    let vigente = true;
    async function revisar() {
      try {
        const salud = await api.salud();
        if (!vigente) return;
        if (salud.base_datos.estado !== "ok") setEstado("sin-base");
        else if (salud.modelo_local.estado !== "ok") setEstado("sin-modelo");
        else setEstado("ok");
      } catch (e) {
        // /health responde 503 cuando algo falla; el cliente lo convierte en error.
        if (!vigente) return;
        const mensaje = String((e as Error).message);
        setEstado(mensaje.includes("conectar") ? "sin-backend" : "sin-modelo");
      }
    }
    revisar();
    const intervalo = setInterval(revisar, 30_000);
    return () => {
      vigente = false;
      clearInterval(intervalo);
    };
  }, []);

  if (estado === "ok") return null;
  const textos: Record<Exclude<Estado, "ok">, string> = {
    "sin-backend": "No hay conexión con el servidor de Patroclo. Las preguntas no se podrán responder.",
    "sin-modelo": "El modelo local no está disponible en este momento. Patroclo no podrá responder hasta que vuelva.",
    "sin-base": "La base de datos no está disponible en este momento.",
  };
  return (
    <div className="aviso aviso-error" role="alert">
      {textos[estado]}
    </div>
  );
}
