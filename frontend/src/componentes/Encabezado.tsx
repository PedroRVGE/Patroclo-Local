import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useSesion } from "../sesion/Sesion";

export default function Encabezado() {
  const { usuario, salir } = useSesion();
  const navegar = useNavigate();
  const { pathname } = useLocation();
  const enChat = pathname === "/" || pathname.startsWith("/chat/");

  async function cerrarSesion() {
    await salir();
    navegar("/ingresar", { replace: true });
  }

  return (
    <header className="encabezado">
      <div className="marca">
        <img src="/queso.svg" alt="" width={34} height={34} />
        <div>
          <div className="marca-nombre">Patroclo</div>
          <div className="marca-sub">experto en lácteos de cabra · Del Pastor</div>
        </div>
      </div>
      <nav className="navegacion">
        {/* «Chat» queda activo también en /chat/<id> (una conversación abierta). */}
        <NavLink to="/" className={() => (enChat ? "activo" : "")}>
          Chat
        </NavLink>
        <NavLink to="/documentos" className={({ isActive }) => (isActive ? "activo" : "")}>
          Documentos
        </NavLink>
      </nav>
      <div className="cuenta">
        <span className="cuenta-nombre" title={usuario?.correo}>
          {usuario?.nombre}
        </span>
        <button className="boton boton-secundario" onClick={cerrarSesion}>
          Cerrar sesión
        </button>
      </div>
    </header>
  );
}
