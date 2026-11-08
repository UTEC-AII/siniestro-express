import { useMemo, useRef, useState } from "react";
import { api } from "./api.js";

const CAMPOS = [
  ["antiguedad_vehiculo", "antigüedad"],
  ["valor_vehiculo", "valor"],
  ["severidad", "severidad"],
  ["tipo_siniestro", "tipo"],
  ["piezas_afectadas", "piezas"],
  ["requiere_grua", "grúa"],
  ["combustible", "combustible"],
];

const SUGERENCIAS = [
  "Me chocaron por atrás, fue leve, dos piezas, no necesité grúa",
  "Me robaron las llantas en el estacionamiento, dos piezas",
  "Choque fuerte, ocho piezas dañadas y necesité grúa",
];

const RUTAS = {
  PAGO_EXPRES: "Pago exprés",
  AJUSTADOR: "Analista",
  PERITAJE: "Peritaje",
  PERDIDA_TOTAL: "Pérdida total",
  REVISION_MANUAL: "Revisión manual",
  DOCUMENTACION_PENDIENTE: "Falta documento",
  PENDIENTE_PREDICCION: "Pendiente",
};

function soles(valor) {
  if (valor === null || valor === undefined) return "—";
  return `S/ ${Number(valor).toLocaleString("es-PE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export default function Chat({ onVerCaso }) {
  const [entrada, setEntrada] = useState("AUTO-2026-8801");
  const [poliza, setPoliza] = useState(null);
  const [chatId, setChatId] = useState(null);
  const [mensajes, setMensajes] = useState([]);
  const [slots, setSlots] = useState({});
  const [expediente, setExpediente] = useState(null);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [subiendo, setSubiendo] = useState(false);
  const [subidas, setSubidas] = useState(0);
  const [pendientes, setPendientes] = useState([]);
  const fin = useRef(null);

  const paso = useMemo(() => {
    if (!poliza) return 1;
    if (expediente) return 3;
    return 2;
  }, [poliza, expediente]);

  async function identificar(evento) {
    evento?.preventDefault();
    setError("");
    setCargando(true);
    try {
      const datos = await api.poliza(entrada.trim());
      const chat = await api.crearChat(datos.poliza_id);
      setPoliza(datos);
      setChatId(chat.chatId);
      setMensajes([
        {
          role: "assistant",
          content:
            `Hola ${(datos.nombre || "").split(" ")[0]}, soy SiniestroExpress de Andes Seguros. ` +
            `Gracias por comunicarte. Veo tu póliza ${datos.poliza_id}: ` +
            `${datos.vehiculo_marca} ${datos.vehiculo_modelo} ${datos.vehiculo_year}. ` +
            `Cuéntame qué pasó con el vehículo.`,
        },
      ]);
    } catch (fallo) {
      setError(`No pudimos cargar la póliza: ${fallo.message}`);
    } finally {
      setCargando(false);
    }
  }

  async function enviar(evento) {
    evento?.preventDefault();
    const limpio = texto.trim();
    if (!limpio || enviando || !chatId || expediente) return;
    setTexto("");
    setError("");
    setMensajes((previos) => [...previos, { role: "user", content: limpio }]);
    setEnviando(true);
    try {
      const respuesta = await api.enviar(chatId, limpio);
      setMensajes((previos) => [
        ...previos,
        { role: "assistant", content: respuesta.respuesta },
      ]);
      setSlots(respuesta.slots || {});
      if (respuesta.expediente && respuesta.expediente.expediente_id) {
        setExpediente(respuesta.expediente);
        setTexto("");
      }
    } catch (fallo) {
      setError(fallo.message);
      setMensajes((previos) => [
        ...previos,
        {
          role: "assistant",
          content:
            "Estamos con un problema técnico. Tu reporte quedó guardado; puedes reintentar en un momento.",
        },
      ]);
    } finally {
      setEnviando(false);
      setTimeout(() => fin.current?.scrollIntoView({ behavior: "smooth", block: "end" }), 60);
    }
  }

  function elegirFotos(evento) {
    const archivos = Array.from(evento.target.files || []);
    if (!archivos.length) return;
    setPendientes((previas) => [
      ...previas,
      ...archivos.map((archivo) => ({ archivo, url: URL.createObjectURL(archivo) })),
    ]);
    evento.target.value = "";
  }

  function quitarFoto(indice) {
    setPendientes((previas) => {
      URL.revokeObjectURL(previas[indice].url);
      return previas.filter((_, i) => i !== indice);
    });
  }

  async function enviarFotos() {
    if (!pendientes.length || !expediente) return;
    setSubiendo(true);
    setError("");
    const claves = [];
    try {
      for (const { archivo } of pendientes) {
        const { upload_url, key } = await api.presignFoto(
          expediente.expediente_id,
          archivo.type
        );
        const subida = await fetch(upload_url, {
          method: "PUT",
          headers: { "Content-Type": archivo.type },
          body: archivo,
        });
        if (!subida.ok) throw new Error("No se pudo subir " + archivo.name);
        claves.push(key);
      }
      await api.registrarFotos(expediente.expediente_id, claves);
      setSubidas((previas) => previas + claves.length);
      pendientes.forEach((foto) => URL.revokeObjectURL(foto.url));
      setPendientes([]);
    } catch (fallo) {
      setError(fallo.message);
    } finally {
      setSubiendo(false);
    }
  }

  function reiniciar() {
    setPoliza(null);
    setChatId(null);
    setMensajes([]);
    setSlots({});
    setExpediente(null);
    setError("");
    setTexto("");
  }

  if (!poliza) {
    return (
      <>
        <header className="head">
          <span className="eyebrow">Paso 1 · Identificación</span>
          <h1>
            Reporta tu siniestro en <em>tres minutos</em>.
          </h1>
          <p className="lead">
            Ingresa tu número de póliza. El agente revisará tus datos, estimará el costo
            de la reparación y te dirá qué sigue.
          </p>
        </header>

        {error && <div className="error">{error}</div>}

        <div className="card" style={{ maxWidth: 460 }}>
          <form onSubmit={identificar} style={{ display: "grid", gap: 12 }}>
            <label className="field">
              <span>Número de póliza</span>
              <input
                type="text"
                value={entrada}
                onChange={(e) => setEntrada(e.target.value)}
                placeholder="AUTO-2026-8801"
                autoComplete="off"
              />
            </label>
            <button className="btn primary block" type="submit" disabled={cargando}>
              {cargando ? "Buscando póliza…" : "Continuar"}
            </button>
          </form>
          <p>Datos de prueba: AUTO-2026-8801 a AUTO-2026-8820</p>
        </div>
      </>
    );
  }

  return (
    <>
      <header className="head with-action">
        <div>
          <span className="eyebrow">
            Paso {paso} · {paso === 3 ? "Resultado" : "Relato del siniestro"}
          </span>
          <h1>
            {poliza.vehiculo_marca} {poliza.vehiculo_modelo}
          </h1>
          <p className="lead">
            Póliza {poliza.poliza_id} · {poliza.nombre} · valor comercial{" "}
            {soles(poliza.valor_vehiculo)}
          </p>
        </div>
        <button className="btn ghost small" type="button" onClick={reiniciar}>
          Nuevo reporte
        </button>
      </header>

      <div className="chips" style={{ marginBottom: 14 }}>
        {CAMPOS.map(([campo, etiqueta]) => {
          const lleno = slots[campo] !== undefined && slots[campo] !== null && slots[campo] !== "";
          return (
            <span key={campo} className={`chip ${lleno ? "on" : ""}`}>
              {etiqueta}
            </span>
          );
        })}
        {slots.tipo_siniestro === "Robo_Parcial" && (
          <span className={`chip ${slots.parte_policial ? "on" : ""}`}>parte policial</span>
        )}
      </div>

      {error && <div className="error">{error}</div>}

      <div className="chat">
        <div className="chat-log">
          {mensajes.map((mensaje, indice) => (
            <div key={indice} className={`msg ${mensaje.role}`}>
              <span className="msg-role">
                {mensaje.role === "user" ? "Asegurado" : "SiniestroExpress"}
              </span>
              <div className="msg-body">{mensaje.content}</div>
            </div>
          ))}

          {enviando && (
            <div className="typing">
              analizando<span>.</span><span>.</span><span>.</span>
            </div>
          )}

          {expediente && (
            <div className="verdict">
              <div className="verdict-top">
                <div>
                  <span className="eyebrow" style={{ marginBottom: 4 }}>
                    {expediente.monto_indemnizable != null ? "Monto a pagar" : "Monto estimado"}
                  </span>
                  <div className="verdict-amount">
                    {soles(expediente.monto_indemnizable ?? expediente.costo_estimado_pen)}
                  </div>
                </div>
                <span className="tag ok">{RUTAS[expediente.ruta] || expediente.ruta}</span>
              </div>
              <div className="verdict-grid">
                <div>
                  <span>Costo estimado</span>
                  <strong>{soles(expediente.costo_estimado_pen)}</strong>
                </div>
                <div>
                  <span>Deducible</span>
                  <strong>{soles(expediente.deducible)}</strong>
                </div>
                <div>
                  <span>Código</span>
                  <strong>{expediente.codigo_seguimiento || "—"}</strong>
                </div>
                <div>
                  <span>Plazo</span>
                  <strong>{expediente.plazo_horas} h</strong>
                </div>
              </div>

              <div className="verdict-acciones">
                <button
                  className="btn primary small"
                  type="button"
                  onClick={() => onVerCaso?.(expediente.codigo_seguimiento)}
                >
                  Ver el seguimiento de mi caso
                </button>
                <span className="leyenda" style={{ margin: 0 }}>
                  Ahí puedes ver la línea de tiempo y volver cuando quieras.
                </span>
              </div>

              {expediente.documentos?.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <span className="eyebrow">Documentos del caso</span>
                  <p className="leyenda" style={{ margin: "0 0 6px" }}>
                    Los pide un asesor cuando el caso avanza. No tienes que hacer nada
                    ahora.
                  </p>
                  <ul className="docs">
                    {expediente.documentos.map((documento) => (
                      <li key={documento}>
                        {documento}
                        {documento.startsWith("DNI") && (
                          <em> · ya figura en tu póliza</em>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div style={{ marginTop: 14 }}>
                <span className="eyebrow">Adelantar las fotos (opcional)</span>
                <p className="leyenda" style={{ margin: "0 0 8px" }}>
                  No cambian el monto. El analista las usa para verificar que el daño
                  coincide con lo que declaraste. Primero las eliges, las revisas y
                  recién las envías.
                </p>

                {pendientes.length > 0 && (
                  <div className="fotos-preview">
                    {pendientes.map((foto, indice) => (
                      <figure key={foto.url}>
                        <img src={foto.url} alt={"Foto " + (indice + 1)} />
                        <button
                          type="button"
                          onClick={() => quitarFoto(indice)}
                          aria-label="Quitar foto"
                        >
                          ×
                        </button>
                      </figure>
                    ))}
                  </div>
                )}

                <div className="fotos-acciones">
                  <label className="btn ghost small">
                    {pendientes.length ? "Elegir otras" : "Elegir fotos"}
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      multiple
                      hidden
                      onChange={elegirFotos}
                      disabled={subiendo}
                    />
                  </label>
                  {pendientes.length > 0 && (
                    <button
                      className="btn primary small"
                      type="button"
                      onClick={enviarFotos}
                      disabled={subiendo}
                    >
                      {subiendo
                        ? "Enviando…"
                        : `Enviar ${pendientes.length} foto${pendientes.length > 1 ? "s" : ""}`}
                    </button>
                  )}
                  {subidas > 0 && (
                    <span className="leyenda" style={{ margin: 0 }}>
                      {subidas} enviada{subidas > 1 ? "s" : ""}
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {mensajes.filter((m) => m.role === "user").length === 0 && !expediente && (
            <div className="sugs">
              <span className="eyebrow">Ejemplos para probar</span>
              {SUGERENCIAS.map((sugerencia) => (
                <button
                  key={sugerencia}
                  className="sug"
                  type="button"
                  onClick={() => setTexto(sugerencia)}
                >
                  {sugerencia}
                </button>
              ))}
            </div>
          )}
          <div ref={fin} />
        </div>

        <form className="composer" onSubmit={enviar}>
          <textarea
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                enviar();
              }
            }}
            placeholder={expediente ? "Caso cerrado. Inicia un nuevo reporte." : "Cuéntame qué pasó…"}
            disabled={enviando || Boolean(expediente)}
            rows={2}
          />
          <button
            className="btn primary"
            type="submit"
            disabled={enviando || !texto.trim() || Boolean(expediente)}
          >
            Enviar
          </button>
        </form>
      </div>
    </>
  );
}
