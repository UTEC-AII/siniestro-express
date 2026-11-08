"""Qué estados puede tomar un expediente y hacia dónde puede moverse.

Un caso rechazado no puede volver a aprobarse: para eso habría que reabrirlo, y eso
es otra acción con su propia auditoría. Aquí solo se permiten transiciones con sentido.
"""

TRANSICIONES = {
    "AJUSTADOR": {"APROBADO", "RECHAZADO"},
    "PERITAJE": {"APROBADO", "RECHAZADO"},
    "REVISION_MANUAL": {"APROBADO", "RECHAZADO"},
    "PENDIENTE_PREDICCION": {"APROBADO", "RECHAZADO"},
    "PERDIDA_TOTAL": {"APROBADO", "RECHAZADO"},
    "DOCUMENTACION_PENDIENTE": {"APROBADO", "RECHAZADO"},
    "PAGO_EXPRES": {"PAGADO"},
    "APROBADO": {"PAGADO"},
    "RECHAZADO": set(),
    "PAGADO": set(),
}


def permitido(actual, nuevo):
    """Indica si el expediente puede pasar de `actual` a `nuevo`."""
    return nuevo in TRANSICIONES.get(actual, set())


def acciones(actual):
    """Acciones que la interfaz debe ofrecer para ese estado."""
    return sorted(TRANSICIONES.get(actual, set()))
