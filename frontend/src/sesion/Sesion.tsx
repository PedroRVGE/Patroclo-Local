// La sesión del usuario: token en memoria + sessionStorage.
//
// sessionStorage (y no localStorage): la sesión dura lo que dura la pestaña. Cerrar el
// navegador la termina, y el token no queda guardado indefinidamente en el equipo.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { alExpirarSesion, api, usarToken } from "../api/cliente";
import type { RespuestaSesion, Usuario } from "../api/tipos";

const CLAVE = "patroclo.sesion";

interface ValorSesion {
  usuario: Usuario | null;
  cargando: boolean; // validando un token guardado al abrir la página
  ingresar: (correo: string, contrasena: string) => Promise<void>;
  registrarse: (correo: string, nombre: string, contrasena: string) => Promise<void>;
  salir: () => Promise<void>;
}

const ContextoSesion = createContext<ValorSesion | null>(null);

function leerGuardada(): { token: string; usuario: Usuario } | null {
  try {
    const crudo = sessionStorage.getItem(CLAVE);
    return crudo ? JSON.parse(crudo) : null;
  } catch {
    return null;
  }
}

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(true);

  const olvidar = useCallback(() => {
    usarToken(null);
    setUsuario(null);
    try {
      sessionStorage.removeItem(CLAVE);
    } catch {
      /* sin almacenamiento: no hay nada que borrar */
    }
  }, []);

  const guardar = useCallback((sesion: RespuestaSesion) => {
    usarToken(sesion.token);
    setUsuario(sesion.usuario);
    try {
      sessionStorage.setItem(CLAVE, JSON.stringify({ token: sesion.token, usuario: sesion.usuario }));
    } catch {
      /* si no se puede guardar, la sesión vive solo en memoria */
    }
  }, []);

  // Al abrir la página: si hay un token guardado, se valida con /yo antes de confiar en él.
  useEffect(() => {
    alExpirarSesion(olvidar);
    const guardada = leerGuardada();
    if (!guardada) {
      setCargando(false);
      return;
    }
    usarToken(guardada.token);
    api
      .yo()
      .then(setUsuario)
      .catch(olvidar)
      .finally(() => setCargando(false));
  }, [olvidar]);

  const valor = useMemo<ValorSesion>(
    () => ({
      usuario,
      cargando,
      ingresar: async (correo, contrasena) => guardar(await api.ingresar(correo, contrasena)),
      registrarse: async (correo, nombre, contrasena) => guardar(await api.registro(correo, nombre, contrasena)),
      salir: async () => {
        try {
          await api.salir(); // revoca el token en el servidor
        } finally {
          olvidar();
        }
      },
    }),
    [usuario, cargando, guardar, olvidar],
  );

  return <ContextoSesion.Provider value={valor}>{children}</ContextoSesion.Provider>;
}

export function useSesion(): ValorSesion {
  const valor = useContext(ContextoSesion);
  if (!valor) throw new Error("useSesion debe usarse dentro de <ProveedorSesion>");
  return valor;
}
