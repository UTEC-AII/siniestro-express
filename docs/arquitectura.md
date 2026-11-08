# Cómo está armado

## El recorrido de un siniestro

```
Asegurado
   |
   v
S3 (SPA React)
   |
   v
API Gateway (agente)  ->  Lambda agente  ->  Groq (gpt-oss-120b)
                              |                    ^
                              |  historial         |
                              v                    |
                        DynamoDB chat -------------+
                              |
                              |  cuando ya tiene los siete datos
                              v
API Gateway (core)  ->  Lambda core  ->  Lambda ml (costo, abandono)
                            |                  ^
                            v                  |
                    DynamoDB polizas    bosques exportados a JSON
                    DynamoDB expedientes
```

En palabras: el asegurado se identifica con su póliza, el agente conversa y anota los
datos en DynamoDB, y cuando ya no falta nada llama a `core`. Ese servicio consulta los
dos modelos, aplica las reglas de la póliza y guarda el expediente con su código de
seguimiento.

## Qué guarda cada tabla

| Tabla | Clave | Índices | Qué contiene |
|---|---|---|---|
| `siniestro-chat-<stage>` | `pk` = `CHAT#<id>`, `sk` = `MSG#<iso>#<rol>` o `META` | — | Mensajes y estado de la conversación |
| `siniestro-polizas-<stage>` | `poliza_id` | GSI `by_cliente` | Póliza, vehículo y deducible |
| `siniestro-expedientes-<stage>` | `expediente_id` | GSI `by_cliente`, `by_estado`, `by_codigo` | Slots, predicciones, liquidación y estado |

El índice `by_estado` no es decorativo: es la consulta que alimenta la cola del
analista. `by_codigo` resuelve el seguimiento del asegurado con un código corto.

## Las tres decisiones que costaron más

### Servir los modelos sin scikit-learn

Los modelos venían entrenados con scikit-learn y se servían en un contenedor sobre
EC2. Para un backend cien por ciento serverless eso no servía. El entrenamiento quedó
en `services/ml/training/` y se reproduce con `train_costo_reparacion.py`,
`train_abandono.py`, `export_models.py` y `verificar_paridad.py`. Las métricas de cada
corrida quedan en `training/models/metricas_*.json` (MAE de S/ 394 y R² de 0.95 en la
última).

El zip con scikit-learn, numpy, scipy y pandas pesa 71 MB. Lambda acepta 50. Probamos
recortar dependencias y no alcanzaba. La salida fue exportar los bosques a JSON
(250 árboles para el costo, 200 para el abandono) y recorrerlos con listas y `struct`.

Tres cosas que aprendimos en el camino:

- El artefacto pasa de 71 MB a 2,4 MB y la predicción de 0,2 ms.
- scikit-learn evalúa los árboles en `float32`. Si el runtime usa `float64`, los
  empates de umbral se resuelven distinto y el monto cambia. Hay que replicar el
  redondeo, no es opcional.
- La paridad se comprueba con 500 casos: la diferencia máxima es de medio céntimo.

### Separar lo que decide el modelo de lo que decide la póliza

El modelo devuelve un costo. Lo que el asegurado cobra es otra cosa: se le resta el
deducible, hay topes por valor comercial y hay siniestros que no se pueden liquidar sin
papeles (un robo sin parte policial).

Por eso el costo estimado y la liquidación son pasos distintos. El primero es del
modelo; el segundo es de `decision.py`, un archivo con reglas legibles y 25 pruebas.

### Fotos que no tocan el monto

El asegurado puede adjuntar hasta seis fotos. No entran al modelo. Sirven para que el
analista compare lo declarado con lo que se ve en la imagen, que es justamente el tipo
de control que hace un ajustador real.

La subida va del navegador directo a S3 con una URL firmada. La Lambda solo firma y
guarda la referencia; nunca transporta la imagen.

```
Navegador  --POST presign-->  Lambda core  --firma-->  URL de 15 minutos
Navegador  --PUT imagen---->  S3 (bucket privado)
Navegador  --POST keys----->  Lambda core  -->  expediente.fotos
Analista   --GET fotos----->  Lambda core  --firma-->  URLs de lectura de 5 minutos
```

## Lo que dejamos fuera a propósito

- **Visión artificial.** Detectar el daño desde la foto pide otro modelo y un conjunto
  etiquetado. El MVP se queda en la decisión, que es donde está la espera.
- **Asignación de taller y proforma.** Requiere un catálogo de talleres de
  reparación por ciudad y reglas de asignación. Es la siguiente pieza del producto.
- **Cognito.** El panel usa un código de demostración guardado en `sessionStorage`.
  Alcanza para el piloto y está anotado como limitación, no como solución.
