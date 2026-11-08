import { useEffect, useState } from "react";
import { api } from "./api.js";

const RUTAS = {
  PAGO_EXPRES: "Pago exprés",
  AJUSTADOR: "Analista",
  PERITAJE: "Peritaje",
  REVISION_MANUAL: "Revisión manual",
  PENDIENTE_PREDICCION: "Pendiente",
  APROBADO: "Aprobado",
  RECHAZADO: "Rechazado",
  PAGADO: "Pagado",
};

function soles(valor) {
  if (valor === null || valor === undefined) return "—";
  return `S/ ${Number(valor).toLocaleString("es-PE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function etapas(caso) {
  const aprobado = ["PAGO_EXPRES", "APROBADO", "PAGADO"].includes(caso.estado);
  const rechazado = caso.estado === "RECHAZADO";
  return [
    {
      nombre: "Reportado",
      hecho: true,
      nota: new Date(caso.creado_en).toLocaleString("es-PE", { dateStyle: "short", timeStyle: "short" }),
    },
    {
      nombre: "Monto estimado",
      hecho: caso.costo_estimado_pen != null,
      nota: soles(caso.costo_estimado_pen),
    },
    {
      nombre: "Atención asignada",
      hecho: Boolean(caso.ruta) && caso.ruta !== "PENDIENTE_PREDICCION",
      nota: RUTAS[caso.ruta] || caso.ruta,
    },
    {
      nombre: rechazado ? "Rechazado" : aprobado ? "Aprobado" : "En revisión",
      hecho: aprobado || rechazado,
      nota: `${caso.plazo_horas} h`,
    },
  ];
}

export default function Caso({ codigo, onVolver }) {
  const [caso, setCaso] = useState(null);
  const [error, setError] = useState("");
  const [copiado, setCopiado] = useState(false);
  const [conversacion, setConversacion] = useState(null);
  const [fotos, setFotos] = useState([]);

  useEffect(() => {
    let activo = true;
    api
      .seguimiento(codigo)
      .then((datos) => {
        if (!activo) return;
        setCaso(datos);
        return api
          .fotos(datos.expediente_id)
          .then((respuesta) => activo && setFotos(respuesta.fotos || []))
          .catch(() => activo && setFotos([]));
      })
      .catch((fallo) => activo && setError(fallo.message));
    return () => {
      activo = false;
    };
  }, [codigo]);

  if (error) {
    return (
      <>
        <header className="head">
          <span className="eyebrow">Seguimiento</span>
          <h1>No encontramos ese caso</h1>
          <p className="lead">Revisa el código: tiene la forma SE-XXXXXX.</p>
        </header>
        <div className="error">{error}</div>
        <button className="btn ghost" type="button" onClick={onVolver}>
          Probar con otro código
        </button>
      </>
    );
  }

  if (!caso) return <p className="typing">Buscando tu caso…</p>;

  const texto =
    `Mi caso en SiniestroExpress: ${caso.codigo_seguimiento}. ` +
    `Estado: ${RUTAS[caso.estado] || caso.estado}. Monto a pagar: ${soles(caso.monto_indemnizable ?? caso.costo_estimado_pen)}.`;

  async function copiar() {
    try {
      await navigator.clipboard.writeText(caso.codigo_seguimiento);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      setCopiado(false);
    }
  }

  async function verConversacion() {
    try {
      const datos = await api.chat(caso.chat_id);
      setConversacion(datos.messages || []);
    } catch (fallo) {
      setError(fallo.message);
    }
  }

  return (
    <>
      <header className="head with-action">
        <div>
          <span className="eyebrow">Seguimiento</span>
          <h1>
            Tu caso <em>{caso.codigo_seguimiento}</em>
          </h1>
          <p className="lead">
            Póliza {caso.poliza_id} · expediente {caso.expediente_id}
          </p>
        </div>
        <button className="btn ghost small" type="button" onClick={onVolver}>
          Otro caso
        </button>
      </header>

      <div className="code-box">
        <div>
          <span className="eyebrow" style={{ marginBottom: 4 }}>
            Código de seguimiento
          </span>
          <div className="code-value">{caso.codigo_seguimiento}</div>
        </div>
        <div className="code-actions">
          <button className="btn ghost small" type="button" onClick={copiar}>
            {copiado ? "Copiado" : "Copiar"}
          </button>
          <a
            className="btn ghost small"
            href={`https://wa.me/?text=${encodeURIComponent(texto)}`}
            target="_blank"
            rel="noreferrer"
          >
            Compartir
          </a>
        </div>
      </div>

      <ol className="timeline">
        {etapas(caso).map((etapa, indice) => (
          <li key={etapa.nombre} className={`timeline-step ${etapa.hecho ? "done" : ""}`}>
            <span className="timeline-index">{String(indice + 1).padStart(2, "0")}</span>
            <strong>{etapa.nombre}</strong>
            <span className="timeline-note">{etapa.nota}</span>
          </li>
        ))}
      </ol>

      <div className="kpi-row" style={{ marginTop: 22 }}>
        <div className="kpi">
          <span>A pagar</span>
          <strong>{soles(caso.monto_indemnizable ?? caso.costo_estimado_pen)}</strong>
        </div>
        <div className="kpi">
          <span>Atención</span>
          <strong>{RUTAS[caso.ruta] || caso.ruta}</strong>
        </div>
        <div className="kpi">
          <span>Plazo</span>
          <strong>{caso.plazo_horas} h</strong>
        </div>
        <div className="kpi">
          <span>Prioridad</span>
          <strong>{caso.prioridad_retencion ? "Retención alta" : "Normal"}</strong>
        </div>
      </div>

      <p className="motivo" style={{ margin: "18px 0" }}>
        {caso.motivo}
      </p>

      <section className="historial">
        <span className="eyebrow">Fotos que enviaste</span>
        {fotos.length === 0 ? (
          <p className="leyenda" style={{ margin: "6px 0 0" }}>
            En este caso no adjuntaste fotos. Si el analista las necesita, un asesor te
            las pedirá.
          </p>
        ) : (
          <div className="fotos" style={{ marginTop: 8 }}>
            {fotos.map((foto) => (
              <a key={foto.key} href={foto.url} target="_blank" rel="noreferrer">
                <img src={foto.url} alt="Foto que enviaste" loading="lazy" />
              </a>
            ))}
          </div>
        )}
      </section>

      {!conversacion ? (
        <button className="btn ghost small" type="button" onClick={verConversacion}>
          Ver la conversación
        </button>
      ) : (
        <section className="historial">
          <span className="eyebrow">Conversación registrada</span>
          {conversacion
            .filter((m) => m.role)
            .map((mensaje) => (
              <div key={mensaje.sk} className={`msg ${mensaje.role}`}>
                <span className="msg-role">
                  {mensaje.role === "user" ? "Asegurado" : "SiniestroExpress"}
                </span>
                <div className="msg-body">{mensaje.content}</div>
              </div>
            ))}
        </section>
      )}
    </>
  );
}
