"""Decide qué hacer con el siniestro y cuánto se paga.

El modelo de ML entrega un costo de reparación, pero eso no es lo que cobra el cliente.
Acá se aplica la póliza: se elige la ruta, se descuenta el deducible y, si la
reparación se lleva más del 75 % del valor del auto, se liquida como pérdida total.

Los umbrales de la ruta salen de la distribución del modelo de costos, que a su vez se
recalculó con precios de taller de Lima. El percentil 75 del grupo leve con dos piezas
o menos está en S/ 791 y el percentil 75 del total en S/ 5,288, así que el pago exprés
corta en S/ 1,000 y el peritaje arranca en S/ 5,000. El deducible (10 % con piso de
S/ 350) y el umbral de pérdida total (75 % del valor comercial) siguen la práctica del
mercado.
"""

PAY_EXPRESS_MAX_PEN = 1000.0
PAY_EXPRESS_MAX_PIEZAS = 2
PERITAJE_MIN_PEN = 5000.0
CHURN_ALTO = 0.55

DEDUCIBLE_PCT = 0.10
DEDUCIBLE_MIN_PEN = 350.0
PERDIDA_TOTAL_UMBRAL = 0.75

PAGO_EXPRES = "PAGO_EXPRES"
AJUSTADOR = "AJUSTADOR"
PERITAJE = "PERITAJE"
PERDIDA_TOTAL = "PERDIDA_TOTAL"
REVISION_MANUAL = "REVISION_MANUAL"
DOCUMENTACION_PENDIENTE = "DOCUMENTACION_PENDIENTE"
PENDIENTE_PREDICCION = "PENDIENTE_PREDICCION"

# Siniestros que nunca se resuelven solo con una foto.
TIPOS_CON_PERITAJE = {"Robo_Parcial", "Inundacion", "Volcadura"}

PLAZOS = {
    PAGO_EXPRES: 24,
    AJUSTADOR: 72,
    PERITAJE: 120,
    PERDIDA_TOTAL: 120,
    REVISION_MANUAL: 48,
    DOCUMENTACION_PENDIENTE: 72,
    PENDIENTE_PREDICCION: 72,
}

DOCUMENTOS = {
    PAGO_EXPRES: ["DNI del asegurado", "Fotos del vehículo"],
    AJUSTADOR: ["DNI del asegurado", "Fotos del vehículo", "Presupuesto del taller"],
    PERITAJE: ["DNI del asegurado", "Fotos del vehículo", "Presupuesto del taller"],
    PERDIDA_TOTAL: ["DNI del asegurado", "Tarjeta de propiedad", "Parte policial"],
    REVISION_MANUAL: ["DNI del asegurado"],
    DOCUMENTACION_PENDIENTE: ["Parte policial"],
    PENDIENTE_PREDICCION: ["DNI del asegurado"],
}

MOTIVOS = {
    PAGO_EXPRES: "Daño menor, sin grúa y con dos piezas o menos: se paga sin inspección.",
    AJUSTADOR: "Caso intermedio: un analista revisa el expediente de forma remota.",
    PERITAJE: "Requiere inspección del vehículo antes de liquidar.",
    PERDIDA_TOTAL: "El costo de reparación supera el 75 % del valor comercial: se indemniza el vehículo.",
    REVISION_MANUAL: "Los datos del relato no son coherentes entre si.",
    DOCUMENTACION_PENDIENTE: "Falta el parte policial que exige la cobertura de robo.",
    PENDIENTE_PREDICCION: "No se pudo estimar el monto; se reintenta la prediccion.",
}


def liquidar(costo_pen, probabilidad_abandono, poliza, slots, coherente=True):
    """Devuelve ruta, plazos, deducible y monto indemnizable."""
    slots = slots or {}
    poliza = poliza or {}

    if not coherente:
        return _salida(REVISION_MANUAL, probabilidad_abandono)

    if costo_pen is None:
        return _salida(PENDIENTE_PREDICCION, probabilidad_abandono)

    costo = float(costo_pen)
    tipo = slots.get("tipo_siniestro")
    valor = float(poliza.get("valor_vehiculo") or 0)
    parte = str(slots.get("parte_policial") or "").strip().upper()
    tiene_parte = parte not in ("", "NO", "NO TIENE", "SIN PARTE", "NINGUNO")

    if tipo == "Robo_Parcial" and not tiene_parte:
        return _salida(DOCUMENTACION_PENDIENTE, probabilidad_abandono, pide_parte=False)

    pct = float(poliza.get("deducible_pct") or DEDUCIBLE_PCT)
    minimo = float(poliza.get("deducible_min") or DEDUCIBLE_MIN_PEN)

    if valor and costo >= valor * PERDIDA_TOTAL_UMBRAL:
        ruta, base = PERDIDA_TOTAL, valor
    elif (
        tipo in TIPOS_CON_PERITAJE
        or costo >= PERITAJE_MIN_PEN
        or slots.get("severidad") == "Grave"
    ):
        ruta, base = PERITAJE, costo
    elif costo <= PAY_EXPRESS_MAX_PEN and _como_entero(slots.get("requiere_grua")) == 0 and _como_entero(slots.get("piezas_afectadas")) <= PAY_EXPRESS_MAX_PIEZAS:
        ruta, base = PAGO_EXPRES, costo
    else:
        ruta, base = AJUSTADOR, costo

    return _salida(ruta, probabilidad_abandono, base=base, pct=pct, minimo=minimo)


def _como_entero(valor):
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return 99


def _salida(ruta, probabilidad_abandono=None, base=None, pide_parte=False, pct=DEDUCIBLE_PCT, minimo=DEDUCIBLE_MIN_PEN):
    deducible = 0.0
    monto = None
    if base is not None:
        deducible = round(max(base * pct, minimo), 2)
        monto = round(max(base - deducible, 0.0), 2)

    documentos = list(DOCUMENTOS[ruta])
    if pide_parte and "Parte policial" not in documentos:
        documentos.append("Parte policial")

    return {
        "ruta": ruta,
        "motivo": MOTIVOS[ruta],
        "plazo_horas": PLAZOS[ruta],
        "prioridad_retencion": bool(
            probabilidad_abandono is not None and float(probabilidad_abandono) >= CHURN_ALTO
        ),
        "base_liquidacion": round(base, 2) if base is not None else None,
        "deducible": deducible if base is not None else None,
        "monto_indemnizable": monto,
        "documentos": documentos,
    }


def esta_aprobada(ruta):
    """El pago exprés nace aprobado; el resto requiere aprobación humana."""
    return ruta == PAGO_EXPRES
