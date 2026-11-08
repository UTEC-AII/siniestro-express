import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";

const FILTROS = [
  ["", "Todos"],
  ["PAGO_EXPRES", "Pago exprés"],
  ["AJUSTADOR", "Analista"],
  ["PERITAJE", "Peritaje"],
  ["REVISION_MANUAL", "Revisión"],
  ["APROBADO", "Aprobados"],
];

const RUTAS = {
  PAGO_EXPRES: "Pago exprés",
  AJUSTADOR: "Analista",
  PERITAJE: "Peritaje",
  PERDIDA_TOTAL: "Pérdida total",
  REVISION_MANUAL: "Revisión manual",
  DOCUMENTACION_PENDIENTE: "Falta documento",
  PENDIENTE_PREDICCION: "Pendiente",
  APROBADO: "Aprobado",
  RECHAZADO: "Rechazado",
  PAGADO: "Pagado",
};

const ACCIONES = {
  PERDIDA_TOTAL: ["APROBADO", "RECHAZADO"],
  DOCUMENTACION_PENDIENTE: ["APROBADO", "RECHAZADO"],
  AJUSTADOR: ["APROBADO", "RECHAZADO"],
  PERITAJE: ["APROBADO", "RECHAZADO"],
  REVISION_MANUAL: ["APROBADO", "RECHAZADO"],
  PENDIENTE_PREDICCION: ["APROBADO", "RECHAZADO"],
  PAGO_EXPRES: ["PAGADO"],
  APROBADO: ["PAGADO"],
  RECHAZADO: [],
  PAGADO: [],
};

const ETIQUETA_ACCION = {
  APROBADO: "Aprobar",
  RECHAZADO: "Rechazar",
  PAGADO: "Marcar pagado",
};

const CLASE = {
  PAGO_EXPRES: "ok",
  APROBADO: "ok",
  PAGADO: "ok",
  AJUSTADOR: "warn",
  PERITAJE: "warn",
  REVISION_MANUAL: "bad",
  RECHAZADO: "bad",
  PERDIDA_TOTAL: "warn",
  DOCUMENTACION_PENDIENTE: "bad",
  PENDIENTE_PREDICCION: "bad",
};

const ETIQUETAS = {
  antiguedad_vehiculo: "Antigüedad",
  valor_vehiculo: "Valor",
  severidad: "Severidad",
  tipo_siniestro: "Tipo",
  piezas_afectadas: "Piezas",
  requiere_grua: "Grúa",
  combustible: "Combustible",
};

const TIPOS = {
  Colision: "Colisión",
  Choque_Multiple: "Choque múltiple",
  Robo_Parcial: "Robo parcial",
  Inundacion: "Inundación",
};

function formatear(campo, valor) {
  if (campo === "valor_vehiculo") return soles(valor);
  if (campo === "antiguedad_vehiculo") return `${valor} años`;
  if (campo === "requiere_grua") return Number(valor) === 1 ? "Sí" : "No";
  if (campo === "tipo_siniestro") return TIPOS[valor] || valor;
  return String(valor);
}

function soles(valor) {
  if (valor === null || valor === undefined) return "—";
  return `S/ ${Number(valor).toLocaleString("es-PE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function porcentajePagoExpres(lista) {
  if (!lista.length) return 0;
  return Math.round((lista.filter((x) => x.ruta === "PAGO_EXPRES").length / lista.length) * 100);
}

function totalAPagar(lista) {
  return lista.reduce(
    (suma, x) => suma + Number(x.monto_indemnizable ?? x.costo_estimado_pen) || suma,
    0
  );
}

export default function Panel() {
  const [filtro, setFiltro] = useState("");
  const [lista, setLista] = useState([]);
  const [seleccion, setSeleccion] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [fotos, setFotos] = useState([]);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError("");
    try {
      const datos = await api.expedientes(filtro ? { estado: filtro } : {});
      setLista(datos.expedientes || []);
    } catch (fallo) {
      setError(`No pudimos cargar los expedientes: ${fallo.message}`);
    } finally {
      setCargando(false);
    }
  }, [filtro]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function verFotos(expedienteId) {
    setFotos([]);
    try {
      const datos = await api.fotos(expedienteId);
      setFotos(datos.fotos || []);
    } catch {
      setFotos([]);
    }
  }

  async function decidir(id, estado) {
    try {
      await api.actualizar(id, estado);
      setSeleccion(null);
      await cargar();
    } catch (fallo) {
      setError(`No se pudo actualizar: ${fallo.message}`);
    }
  }

  return (
    <>
      <header className="head with-action">
        <div>
          <span className="eyebrow">Panel del analista</span>
          <h1>
            Cola de <em>expedientes</em>
          </h1>
          <p className="lead">
            Cada caso llega con el monto estimado, la ruta sugerida y la evidencia de los
            datos extraídos. La decisión final es del analista.
          </p>
        </div>
        <div className="acciones">
          <a className="btn ghost small" href={api.csvUrl()} target="_blank" rel="noreferrer">
            Descargar CSV
          </a>
        </div>
      </header>

      <div className="kpi-row" style={{ marginBottom: 22 }}>
        <div className="kpi">
          <span>En la vista</span>
          <strong>{lista.length}</strong>
        </div>
        <div className="kpi">
          <span>Pago exprés</span>
          <strong>{porcentajePagoExpres(lista)}%</strong>
        </div>
        <div className="kpi">
          <span>A pagar</span>
          <strong>{soles(totalAPagar(lista))}</strong>
        </div>
        <div className="kpi">
          <span>Retención alta</span>
          <strong>{lista.filter((x) => x.prioridad_retencion).length}</strong>
        </div>
      </div>

      <dl className="glosario">
        <div>
          <dt>Atención</dt>
          <dd>Cómo se resuelve el caso: pago exprés, revisión de un analista, peritaje o pérdida total.</dd>
        </div>
        <div>
          <dt>A pagar</dt>
          <dd>Costo de la reparación menos el deducible de la póliza.</dd>
        </div>
        <div>
          <dt>Abandono</dt>
          <dd>Probabilidad estimada de que el asegurado no renueve su póliza. Se calcula con el modelo de abandono.</dd>
        </div>
      </dl>

      <div className="toolbar">
        <div className="tabs">
          {FILTROS.map(([valor, etiqueta]) => (
            <button
              key={valor || "todos"}
              className={`btn small ${filtro === valor ? "primary" : "ghost"}`}
              onClick={() => setFiltro(valor)}
              type="button"
            >
              {etiqueta}
            </button>
          ))}
        </div>
        <button className="link" type="button" onClick={cargar}>
          {cargando ? "Actualizando…" : "Actualizar"}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="table-wrap">
        <table className="results">
          <thead>
            <tr>
              <th>Expediente</th>
              <th>Cliente</th>
              <th>Atención</th>
              <th>Estado</th>
              <th>Monto</th>
              <th>Abandono</th>
            </tr>
          </thead>
          <tbody>
            {lista.length === 0 && (
              <tr>
                <td colSpan={6} className="empty">
                  {cargando ? "Cargando…" : "Todavía no hay expedientes registrados."}
                </td>
              </tr>
            )}
            {lista.map((item) => (
              <tr
                key={item.expediente_id}
                className={seleccion?.expediente_id === item.expediente_id ? "selected" : ""}
                onClick={() => {
                  setSeleccion(item);
                  verFotos(item.expediente_id);
                }}
              >
                <td data-label="Expediente">{item.expediente_id}</td>
                <td data-label="Cliente">{item.cliente_id}</td>
                <td data-label="Atención">{RUTAS[item.ruta] || item.ruta}</td>
                <td data-label="Estado">
                  <span className={`tag ${CLASE[item.estado] || ""}`}>
                    {RUTAS[item.estado] || item.estado}
                  </span>
                </td>
                <td data-label="A pagar" className="num">
                  {soles(item.monto_indemnizable ?? item.costo_estimado_pen)}
                </td>
                <td data-label="Abandono" className="num">
                  {item.probabilidad_abandono !== undefined
                    ? Number(item.probabilidad_abandono).toFixed(2)
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {seleccion && (
        <section className="detail">
          <div>
            <h2>{seleccion.expediente_id}</h2>
            <p className="motivo">{seleccion.motivo}</p>
          </div>

          <div className="kpi-row">
            <div className="kpi">
              <span>A pagar</span>
              <strong>{soles(seleccion.monto_indemnizable ?? seleccion.costo_estimado_pen)}</strong>
            </div>
            <div className="kpi">
              <span>Costo / deducible</span>
              <strong>
                {soles(seleccion.costo_estimado_pen)}
                {seleccion.deducible != null ? ` / ${soles(seleccion.deducible)}` : ""}
              </strong>
            </div>
            <div className="kpi">
              <span>Atención</span>
              <strong>{RUTAS[seleccion.ruta] || seleccion.ruta}</strong>
            </div>
            <div className="kpi">
              <span>Plazo</span>
              <strong>{seleccion.plazo_horas} h</strong>
            </div>
            <div className="kpi">
              <span>Riesgo de abandono</span>
              <strong>
                {seleccion.probabilidad_abandono !== undefined
                  ? Number(seleccion.probabilidad_abandono).toFixed(2)
                  : "—"}
              </strong>
            </div>
          </div>

          <div>
            <span className="eyebrow">Datos extraídos por el agente</span>
            <div className="chips">
              {Object.entries(seleccion.slots || {}).map(([clave, valor]) => (
                <span key={clave} className="chip on">
                  {ETIQUETAS[clave] || clave}: {formatear(clave, valor)}
                </span>
              ))}
            </div>
          </div>

          {fotos.length > 0 && (
            <div>
              <span className="eyebrow">
                Fotos del asegurado: verifica que el daño coincida con lo declarado
              </span>
              <div className="fotos">
                {fotos.map((foto) => (
                  <a key={foto.key} href={foto.url} target="_blank" rel="noreferrer">
                    <img src={foto.url} alt="Foto del siniestro" loading="lazy" />
                  </a>
                ))}
              </div>
            </div>
          )}

          <div className="acciones">
            {(ACCIONES[seleccion.estado] || []).map((accion) => (
              <button
                key={accion}
                className={`btn small ${accion === "RECHAZADO" ? "ghost" : "primary"}`}
                type="button"
                onClick={() => decidir(seleccion.expediente_id, accion)}
              >
                {ETIQUETA_ACCION[accion]}
              </button>
            ))}
            {(ACCIONES[seleccion.estado] || []).length === 0 && (
              <span className="leyenda" style={{ margin: 0 }}>
                Caso cerrado: {RUTAS[seleccion.estado] || seleccion.estado}. No admite más
                cambios.
              </span>
            )}
            <button className="link" type="button" onClick={() => setSeleccion(null)}>
              Cerrar
            </button>
          </div>
        </section>
      )}
    </>
  );
}
