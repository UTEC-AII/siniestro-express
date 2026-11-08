import { useEffect, useState } from "react";
import Caso from "./Caso.jsx";
import Chat from "./Chat.jsx";
import Landing from "./Landing.jsx";
import Panel from "./Panel.jsx";
import { configurado } from "./api.js";

const CLAVE = "siniestro.analista";

export default function App() {
  const [vista, setVista] = useState("inicio");
  const [analista, setAnalista] = useState(false);
  const [codigoCaso, setCodigoCaso] = useState("");

  useEffect(() => {
    setAnalista(sessionStorage.getItem(CLAVE) === "1");
  }, []);

  function entrarComoAnalista() {
    sessionStorage.setItem(CLAVE, "1");
    setAnalista(true);
    setVista("panel");
  }

  function salir() {
    sessionStorage.removeItem(CLAVE);
    setAnalista(false);
    setVista("inicio");
  }

  const items = [
    { id: "inicio", num: "00", label: "Inicio" },
    { id: "reportar", num: "01", label: "Reportar" },
    { id: "panel", num: "02", label: "Panel", bloqueado: !analista },
  ];

  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={(e) => e.preventDefault()}>
          <span className="brand-mark" aria-hidden="true">
            S<span>✓</span>
          </span>
          <span className="brand-text">
            <strong>SiniestroExpress</strong>
            <span>Andes Seguros</span>
          </span>
        </a>

        <nav className="nav" aria-label="Secciones">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${vista === item.id ? "active" : ""} ${
                item.bloqueado ? "locked" : ""
              }`}
              onClick={() => setVista(item.bloqueado ? "inicio" : item.id)}
            >
              <span className="nav-num">{item.num}</span>
              <span className="nav-label">{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-foot">
          <span>
            <strong>Andes Seguros</strong>
            <br />
            canal digital de siniestros
          </span>
          <span>Datos de demostración. Los montos son estimaciones.</span>
          {analista && (
            <button className="link" type="button" onClick={salir}>
              Cerrar sesión
            </button>
          )}
        </div>
      </aside>

      <main className="main">
        {!configurado && (
          <div className="banner">
            <strong>API sin configurar.</strong> Define <code>VITE_AGENTE_API</code> y{" "}
            <code>VITE_CORE_API</code> con las URL de API Gateway y vuelve a compilar.
          </div>
        )}

        {vista === "inicio" && (
          <Landing
            onAsegurado={() => setVista("reportar")}
            onAnalista={entrarComoAnalista}
            onConsultar={(codigo) => {
              setCodigoCaso(codigo);
              setVista("caso");
            }}
          />
        )}

        {vista === "caso" && <Caso codigo={codigoCaso} onVolver={() => setVista("inicio")} />}

        {vista === "reportar" && (
          <Chat
            onVerCaso={(codigo) => {
              setCodigoCaso(codigo);
              setVista("caso");
            }}
          />
        )}

        {vista === "panel" &&
          (analista ? (
            <Panel />
          ) : (
            <Landing
              onAsegurado={() => setVista("reportar")}
              onAnalista={entrarComoAnalista}
              onConsultar={(codigo) => {
                setCodigoCaso(codigo);
                setVista("caso");
              }}
            />
          ))}
      </main>
    </div>
  );
}
