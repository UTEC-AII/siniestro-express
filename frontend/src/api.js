/**
 * Cliente de las dos APIs.
 * VITE_AGENTE_API: URL base del servicio de chat (hasta /dev)
 * VITE_CORE_API:   URL base de pólizas y expedientes (hasta /dev)
 */
const AGENTE = (import.meta.env.VITE_AGENTE_API || "").replace(/\/$/, "");
const CORE = (import.meta.env.VITE_CORE_API || "").replace(/\/$/, "");

export const configurado = Boolean(AGENTE && CORE);
export const urls = { agente: AGENTE, core: CORE };

async function pedir(url, opciones = {}) {
  const respuesta = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...opciones,
  });
  const texto = await respuesta.text();
  let cuerpo = null;
  try {
    cuerpo = texto ? JSON.parse(texto) : null;
  } catch {
    cuerpo = { detalle: texto };
  }
  if (!respuesta.ok) {
    // El backend ya devuelve un texto para el usuario en `respuesta`.
    // Se prefiere ese mensaje al codigo interno del error.
    const mensaje = cuerpo?.respuesta || cuerpo?.error || `HTTP ${respuesta.status}`;
    const fallo = new Error(mensaje);
    fallo.detalle = cuerpo;
    throw fallo;
  }
  return cuerpo;
}

export const api = {
  poliza: (polizaId) => pedir(`${CORE}/polizas/${encodeURIComponent(polizaId)}`),
  crearChat: (polizaId) =>
    pedir(`${AGENTE}/chats`, {
      method: "POST",
      body: JSON.stringify({ poliza_id: polizaId }),
    }),
  enviar: (chatId, prompt) =>
    pedir(`${AGENTE}/chats/${chatId}/messages`, {
      method: "POST",
      body: JSON.stringify({ prompt }),
    }),
  expedientes: (filtro = {}) => {
    const consulta = new URLSearchParams();
    if (filtro.estado) consulta.set("estado", filtro.estado);
    if (filtro.cliente) consulta.set("cliente_id", filtro.cliente);
    const sufijo = consulta.toString() ? `?${consulta}` : "";
    return pedir(`${CORE}/expedientes${sufijo}`);
  },
  actualizar: (expedienteId, estado, nota = "") =>
    pedir(`${CORE}/expedientes/${expedienteId}`, {
      method: "PATCH",
      body: JSON.stringify({ estado, nota }),
    }),
  seguimiento: (codigo) => pedir(`${CORE}/seguimiento/${encodeURIComponent(codigo)}`),
  chat: (chatId) => pedir(`${AGENTE}/chats/${chatId}`),
  presignFoto: (expedienteId, contentType) =>
    pedir(`${CORE}/expedientes/${expedienteId}/fotos/presign`, {
      method: "POST",
      body: JSON.stringify({ content_type: contentType }),
    }),
  registrarFotos: (expedienteId, keys) =>
    pedir(`${CORE}/expedientes/${expedienteId}/fotos`, {
      method: "POST",
      body: JSON.stringify({ keys }),
    }),
  fotos: (expedienteId) => pedir(`${CORE}/expedientes/${expedienteId}/fotos`),
  csvUrl: (sep) => `${CORE}/export${sep ? `?sep=${encodeURIComponent(sep)}` : ""}`,
};
