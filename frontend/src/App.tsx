import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import AvisoServicio from "./componentes/AvisoServicio";
import Encabezado from "./componentes/Encabezado";
import Chat from "./paginas/Chat";
import Documentos from "./paginas/Documentos";
import Ingreso from "./paginas/Ingreso";
import { useSesion } from "./sesion/Sesion";

/** Sin sesión válida → a la pantalla de ingreso (recordando a dónde iba). */
function RutaProtegida() {
  const { usuario, cargando } = useSesion();
  const ubicacion = useLocation();
  if (cargando) return <div className="cargando-pagina">Cargando…</div>;
  if (!usuario) return <Navigate to="/ingresar" replace state={{ desde: ubicacion.pathname }} />;
  return (
    <div className="app">
      <Encabezado />
      <AvisoServicio />
      <main className="contenido">
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/ingresar" element={<Ingreso />} />
      <Route element={<RutaProtegida />}>
        <Route path="/" element={<Chat />} />
        <Route path="/chat/:id" element={<Chat />} />
        <Route path="/documentos" element={<Documentos />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
