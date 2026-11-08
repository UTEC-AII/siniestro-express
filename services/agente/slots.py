"""Normalización y validación de los datos que extrae el modelo.

Es la defensa contra la trampa silenciosa: si un enum llega mal escrito, el
modelo de ML no falla, simplemente predice basura. Aquí se canonicaliza antes.
"""

import unicodedata

CAMPOS = [
    "antiguedad_vehiculo",
    "valor_vehiculo",
    "severidad",
    "tipo_siniestro",
    "piezas_afectadas",
    "requiere_grua",
    "combustible",
]

VALORES = {
    "severidad": ["Leve", "Media", "Grave"],
    "tipo_siniestro": [
        "Choque_Multiple",
        "Colision",
        "Inundacion",
        "Robo_Parcial",
        "Volcadura",
    ],
    "combustible": ["Diesel", "Electrico", "Gasolina", "Hibrido"],
}

ETIQUETAS = {
    "severidad": "la severidad",
    "tipo_siniestro": "el tipo de siniestro",
    "combustible": "el combustible",
}

# Cómo se le ofrecen las opciones al asegurado, en castellano natural.
OPCIONES = {
    "Leve": "leve",
    "Media": "media",
    "Grave": "grave",
    "Choque_Multiple": "choque múltiple",
    "Colision": "colisión",
    "Inundacion": "inundación",
    "Robo_Parcial": "robo parcial",
    "Volcadura": "volcadura",
    "Diesel": "diésel",
    "Electrico": "eléctrico",
    "Gasolina": "gasolina",
    "Hibrido": "híbrido",
}

# El asegurado no dice numeros: dice "todo el carro" o "varias".
PIEZAS_EN_PALABRAS = {
    "todo el carro": 14, "todo": 14, "todos": 14, "completo": 14, "completa": 14,
    "todas": 14, "entero": 14, "entera": 14, "todo el vehiculo": 14,
    "la mitad": 6, "medio carro": 6, "medio": 6,
    "varias": 5, "varios": 5, "algunas": 3, "algunos": 3, "pocas": 2, "pocas piezas": 2,
    "una": 1, "una sola": 1, "solo una": 1,
}

RANGOS = {
    "antiguedad_vehiculo": (0, 40),
    "valor_vehiculo": (5000, 400000),
    "piezas_afectadas": (1, 14),
}


def _texto(value):
    """Minúsculas, sin acentos y con guiones o guiones bajos convertidos en espacios.

    Sin esto, `Robo_Parcial` y `robo parcial` serían valores distintos y el slot se
    descartaría en silencio, dejando al agente preguntando para siempre.
    """
    raw = str(value).strip().lower().replace("_", " ").replace("-", " ")
    normalizado = unicodedata.normalize("NFKD", raw)
    limpio = "".join(c for c in normalizado if not unicodedata.combining(c))
    return " ".join(limpio.split())


def _tabla(campo, alias):
    """Valores canónicos más sus alias; el canónico siempre se reconoce a sí mismo."""
    tabla = {_texto(valor): valor for valor in VALORES[campo]}
    tabla.update(alias)
    return tabla


SEVERIDAD = _tabla(
    "severidad",
    {
        "baja": "Leve", "menor": "Leve", "rayon": "Leve", "ligera": "Leve",
        "moderada": "Media", "moderado": "Media", "intermedia": "Media",
        "alta": "Grave", "severa": "Grave", "severo": "Grave", "fuerte": "Grave",
        "total": "Grave",
    },
)

TIPO = _tabla(
    "tipo_siniestro",
    {
        "choque": "Colision", "impacto": "Colision", "golpe": "Colision",
        "multiple": "Choque_Multiple", "choque multiple": "Choque_Multiple",
        "volteo": "Volcadura", "volco": "Volcadura", "volcamiento": "Volcadura",
        "robo": "Robo_Parcial", "hurto": "Robo_Parcial", "roban": "Robo_Parcial",
        "robaron": "Robo_Parcial", "robo de piezas": "Robo_Parcial",
        "llantas": "Robo_Parcial", "agua": "Inundacion", "lluvia": "Inundacion",
    },
)

COMBUSTIBLE = _tabla(
    "combustible",
    {
        "gas": "Gasolina", "bencina": "Gasolina", "gnv": "Gasolina", "glp": "Gasolina",
        "petroleo": "Diesel", "diesel": "Diesel",
        "electricidad": "Electrico", "bateria": "Electrico",
        "hibrido": "Hibrido", "hibrida": "Hibrido",
    },
)

TABLAS = {"severidad": SEVERIDAD, "tipo_siniestro": TIPO, "combustible": COMBUSTIBLE}

SI_NO = {
    "si": 1, "true": 1, "1": 1, "yes": 1, "claro": 1, "afirmativo": 1, "obvio": 1,
    "no": 0, "false": 0, "0": 0, "nunca": 0, "negativo": 0, "ninguna": 0,
}


def normalizar(raw):
    """Devuelve (slots_validos, errores). Descarta lo que no se puede canonicalizar."""
    slots, errores = {}, []
    raw = raw or {}

    for campo, tabla in TABLAS.items():
        valor = raw.get(campo)
        if valor in (None, ""):
            continue
        clave = _texto(valor)
        if clave in tabla:
            slots[campo] = tabla[clave]
        else:
            errores.append(f"{campo} no reconocido: {valor}")

    for campo, (minimo, maximo) in RANGOS.items():
        valor = raw.get(campo)
        if valor in (None, ""):
            continue
        if campo == "piezas_afectadas":
            clave = _texto(valor)
            if clave in PIEZAS_EN_PALABRAS:
                slots[campo] = PIEZAS_EN_PALABRAS[clave]
                continue
        try:
            numero = float(str(valor).replace(",", ".").split()[0])
        except (ValueError, IndexError):
            errores.append(f"{campo} no es numerico: {valor}")
            continue
        if not minimo <= numero <= maximo:
            errores.append(f"{campo} fuera de rango ({minimo}-{maximo}): {numero}")
            continue
        slots[campo] = int(numero) if campo in ("antiguedad_vehiculo", "piezas_afectadas") else numero

    if raw.get("parte_policial") not in (None, ""):
        slots["parte_policial"] = _limpiar_texto(raw["parte_policial"])

    if raw.get("requiere_grua") not in (None, ""):
        clave = _texto(raw["requiere_grua"])
        if clave in SI_NO:
            slots["requiere_grua"] = SI_NO[clave]
        else:
            errores.append(f"requiere_grua no reconocido: {raw['requiere_grua']}")

    return slots, errores


def _limpiar_texto(valor):
    return " ".join(str(valor or "").strip().split())[:60]


def faltantes(slots):
    """Campos obligatorios que aun no se conocen (calculado, no confiado al LLM).

    El parte policial solo se exige cuando el siniestro es un robo: es la regla de
    la cobertura, no un capricho del formulario.
    """
    pendientes = [campo for campo in CAMPOS if slots.get(campo) in (None, "")]
    if slots.get("tipo_siniestro") == "Robo_Parcial" and not slots.get("parte_policial"):
        pendientes.append("parte_policial")
    return pendientes


def fusionar(base, nuevos):
    """Los valores nuevos pisan a los previos, sin perder lo ya recolectado."""
    resultado = dict(base or {})
    for clave, valor in (nuevos or {}).items():
        if valor not in (None, ""):
            resultado[clave] = valor
    return resultado


def sugerencia(errores):
    """Mensaje determinista con las opciones válidas, para no quedar en bucle."""
    for error in errores or []:
        campo = error.split(" ")[0]
        if campo in VALORES:
            opciones = [OPCIONES.get(valor, valor.lower()) for valor in VALORES[campo]]
            lista = ", ".join(opciones[:-1]) + f" o {opciones[-1]}"
            return f"Perdona, {ETIQUETAS[campo]} solo puede ser {lista}. ¿Cuál de ellos fue?"
    return None
