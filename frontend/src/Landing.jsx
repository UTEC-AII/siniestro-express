import { useState } from "react";

const CODIGO = import.meta.env.VITE_ANALISTA_CODE || "ANALISTA-2026";

export default function Landing({ onAsegurado, onAnalista, onConsultar }) {
  const [analista, setAnalista] = useState("");
  const [errorAnalista, setErrorAnalista] = useState("");
  const [codigo, setCodigo] = useState("");
  const [errorCaso, setErrorCaso] = useState("");

  function entrar(evento) {
    evento.preventDefault();
    if (analista.trim().toUpperCase() === CODIGO.toUpperCase()) {
      setErrorAnalista("");
      onAnalista();
    } else {
      setErrorAnalista("Código incorrecto.");
    }
  }

  function consultar(evento) {
    evento.preventDefault();
    const limpio = codigo.trim().toUpperCase();
    if (!/^SE-[A-Z0-9]{6}$/.test(limpio)) {
      setErrorCaso("Formato esperado: SE-XXXXXX");
      return;
    }
    setErrorCaso("");
    onConsultar(limpio);
  }

  return (
    <div className="home">
      <section className="hero">
        <span className="eyebrow">Siniestros vehiculares</span>
        <h1>
          Reporta tu siniestro en <em>tres minutos</em>.
        </h1>
        <p className="lead">
          Cuéntale al agente qué pasó. Estimamos el daño y te decimos si calificas a
          pago exprés, a revisión de un analista o a peritaje.
        </p>
        <button className="btn primary" type="button" onClick={onAsegurado}>
          Reportar un siniestro
        </button>
        <p className="hero-note">Sin formularios ni llamadas. Cuatro preguntas.</p>

        <ol className="pasos">
          <li>
            <span>01</span>
            <strong>Cuentas qué pasó</strong>
            <em>Como se lo contarías a un amigo.</em>
          </li>
          <li>
            <span>02</span>
            <strong>Estimamos el daño</strong>
            <em>Dos modelos entrenados calculan el monto.</em>
          </li>
          <li>
            <span>03</span>
            <strong>Recibes la ruta y el plazo</strong>
            <em>Pago exprés, analista o peritaje.</em>
          </li>
        </ol>
      </section>

      <div className="grid-2">
        <section className="card">
          <span className="eyebrow">Seguimiento</span>
          <h2>Ya reporté un caso</h2>
          <p>Consulta el estado con el código que te entregamos al terminar.</p>
          <form className="form-inline" onSubmit={consultar}>
            <input
              type="text"
              value={codigo}
              onChange={(e) => setCodigo(e.target.value)}
              placeholder="SE-ABC123"
              autoComplete="off"
              aria-label="Código de seguimiento"
            />
            <button className="btn ghost" type="submit">
              Ver
            </button>
          </form>
          {errorCaso && <span className="nota">{errorCaso}</span>}
        </section>

        <section className="card">
          <span className="eyebrow">Analista</span>
          <h2>Entrar al panel</h2>
          <p>Cola de expedientes, montos estimados y aprobación de casos.</p>
          <form className="form-inline" onSubmit={entrar}>
            <input
              type="text"
              value={analista}
              onChange={(e) => setAnalista(e.target.value)}
              placeholder="Código de analista"
              autoComplete="off"
              aria-label="Código de analista"
            />
            <button className="btn ghost" type="submit">
              Entrar
            </button>
          </form>
          {errorAnalista && <span className="nota">{errorAnalista}</span>}
        </section>
      </div>
    </div>
  );
}
