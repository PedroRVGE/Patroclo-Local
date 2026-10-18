import { useState, type ReactNode, type SyntheticEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ErrorApi } from "../api/cliente";
import { useSesion } from "../sesion/Sesion";

type Modo = "ingresar" | "registrarse";
const CORREO_VALIDO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function Ingreso() {
  const { usuario, ingresar, registrarse } = useSesion();
  const navegar = useNavigate();
  const ubicacion = useLocation();
  const [modo, setModo] = useState<Modo>("ingresar");
  const [correo, setCorreo] = useState("");
  const [nombre, setNombre] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [errorGeneral, setErrorGeneral] = useState("");
  const [enviando, setEnviando] = useState(false);

  const destino = (ubicacion.state as { desde?: string } | null)?.desde ?? "/";
  if (usuario) return <Navigate to={destino} replace />;

  function validar(): Record<string, string> {
    const e: Record<string, string> = {};
    if (!CORREO_VALIDO.test(correo.trim())) e.correo = "Escribe un correo válido.";
    if (modo === "registrarse") {
      if (!nombre.trim()) e.nombre = "Escribe tu nombre.";
      if (contrasena.length < 8) e.contrasena = "Mínimo 8 caracteres.";
      else if (contrasena.length > 128) e.contrasena = "Máximo 128 caracteres.";
      if (confirmacion !== contrasena) e.confirmacion = "Las contraseñas no coinciden.";
    } else if (!contrasena) {
      e.contrasena = "Escribe tu contraseña.";
    }
    return e;
  }

  async function enviar(evento: SyntheticEvent) {
    evento.preventDefault();
    setErrorGeneral("");
    const e = validar();
    setErrores(e);
    if (Object.keys(e).length) return;

    setEnviando(true);
    try {
      if (modo === "ingresar") await ingresar(correo.trim(), contrasena);
      else await registrarse(correo.trim(), nombre.trim(), contrasena);
      navegar(destino, { replace: true });
    } catch (err) {
      setErrorGeneral(err instanceof ErrorApi ? err.message : "Ocurrió un error inesperado.");
    } finally {
      setEnviando(false);
    }
  }

  function cambiarModo(nuevo: Modo) {
    setModo(nuevo);
    setErrores({});
    setErrorGeneral("");
  }

  return (
    <div className="pagina-ingreso">
      <div className="tarjeta-ingreso">
        <div className="ingreso-marca">
          <img src="/queso.svg" alt="" width={56} height={56} />
          <h1>Patroclo</h1>
          <p>experto en lácteos de cabra · Del Pastor</p>
        </div>

        <div className="pestanas" role="tablist">
          <button role="tab" aria-selected={modo === "ingresar"} className={modo === "ingresar" ? "activa" : ""} onClick={() => cambiarModo("ingresar")}>
            Ingresar
          </button>
          <button role="tab" aria-selected={modo === "registrarse"} className={modo === "registrarse" ? "activa" : ""} onClick={() => cambiarModo("registrarse")}>
            Crear cuenta
          </button>
        </div>

        <form onSubmit={enviar} noValidate>
          <Campo etiqueta="Correo" error={errores.correo}>
            <input type="email" autoComplete="email" value={correo} onChange={(e) => setCorreo(e.target.value)} />
          </Campo>
          {modo === "registrarse" && (
            <Campo etiqueta="Nombre" error={errores.nombre}>
              <input autoComplete="name" maxLength={100} value={nombre} onChange={(e) => setNombre(e.target.value)} />
            </Campo>
          )}
          <Campo etiqueta="Contraseña" error={errores.contrasena}>
            <input
              type="password"
              autoComplete={modo === "ingresar" ? "current-password" : "new-password"}
              value={contrasena}
              onChange={(e) => setContrasena(e.target.value)}
            />
          </Campo>
          {modo === "registrarse" && (
            <Campo etiqueta="Repite la contraseña" error={errores.confirmacion}>
              <input type="password" autoComplete="new-password" value={confirmacion} onChange={(e) => setConfirmacion(e.target.value)} />
            </Campo>
          )}

          {errorGeneral && (
            <div className="aviso aviso-error" role="alert">
              {errorGeneral}
            </div>
          )}

          <button type="submit" className="boton boton-principal boton-ancho" disabled={enviando}>
            {enviando ? "Un momento…" : modo === "ingresar" ? "Ingresar" : "Crear cuenta"}
          </button>
        </form>
      </div>
    </div>
  );
}

function Campo({ etiqueta, error, children }: { etiqueta: string; error?: string; children: ReactNode }) {
  return (
    <label className={`campo ${error ? "campo-con-error" : ""}`}>
      <span>{etiqueta}</span>
      {children}
      {error && <small className="campo-error">{error}</small>}
    </label>
  );
}
