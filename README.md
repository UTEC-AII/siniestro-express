# SiniestroExpress

El asegurado choca, entra a un chat y cuenta qué pasó. En la misma conversación recibe
cuánto le van a pagar y en cuánto tiempo. Del otro lado, el analista encuentra el caso
ya armado: monto, ruta sugerida y la evidencia de lo que el cliente declaró.

Proyecto Final de Cloud Computing (MCD8007), UTEC Posgrado. El código vive en la
organización [UTEC-AII](https://github.com/UTEC-AII).

## Los tres servicios

| Servicio | Qué resuelve | Tablas |
|---|---|---|
| `services/agente` | Conversa, entiende el relato y guarda el historial | `siniestro-chat-<stage>` |
| `services/core` | Pólizas, expedientes, reglas de la póliza y fotos | `siniestro-polizas-<stage>`, `siniestro-expedientes-<stage>` |
| `services/ml` | Estima el costo de reparación y el riesgo de abandono | — |

Todo corre en AWS: API Gateway, Lambda con Python 3.14, DynamoDB y S3. Nada de
servidores encendidos.

## La decisión no la toma el modelo

Groq entiende el relato y redacta las respuestas, pero no decide nada. La ruta y el
monto salen de un módulo de reglas que se puede leer y probar:

| Situación | Ruta | Plazo |
|---|---|---|
| Falta el parte policial en un robo | `DOCUMENTACION_PENDIENTE` | 72 h |
| La reparación supera el 75 % del valor del auto | `PERDIDA_TOTAL` | 120 h |
| Robo, inundación, volcadura o severidad grave | `PERITAJE` | 120 h |
| Costo desde S/ 5,000 | `PERITAJE` | 120 h |
| Hasta S/ 1,000, sin grúa y con dos piezas o menos | `PAGO_EXPRES` | 24 h |
| Cualquier otro caso | `AJUSTADOR` | 72 h |
| Datos incoherentes | `REVISION_MANUAL` | 48 h |

El monto que ve el cliente no es el costo de reparación: es el costo menos el
deducible de su póliza. Los umbrales no salieron de la intuición; se calibraron con la
distribución del modelo (el percentil 75 del grupo leve con dos piezas está en S/ 791 y
el del total de casos en S/ 5,288).

## Los términos, en claro

Algunas palabras del dominio no son obvias. Estas son las que usa el sistema:

| Término | Qué significa |
|---|---|
| **Expediente** | El registro del caso: número, datos declarados, monto, atención asignada y estado |
| **Atención** | Cómo se resuelve: pago exprés, analista, peritaje o pérdida total |
| **Pago exprés** | Daño menor: se paga sin que nadie inspeccione el auto |
| **Analista** | Revisión remota del expediente, sin visita al vehículo |
| **Peritaje** | Un perito inspecciona el auto antes de liquidar |
| **Pérdida total** | La reparación cuesta más del 75 % del valor del auto: se indemniza el vehículo |
| **Deducible** | La parte del daño que paga el asegurado; acá es 10 % con un piso de S/ 350 |
| **A pagar** | Costo de reparación menos deducible: lo que efectivamente cobra el asegurado |
| **Abandono** | Probabilidad de que el asegurado no renueve su póliza |

## Sobre los montos

Los modelos se entrenaron con 1,000 siniestros sintéticos. Al principio los importes
estaban muy por encima de la realidad: el mínimo era S/ 1,924 y no había un solo caso
menor a S/ 1,000, cuando la mayoría de los reclamos de auto son un rayón o un espejo.

Se recalcularon con una fórmula de taller y precios de Lima: repuesto alternativo más
pintura y mano de obra por pieza, un factor mayor para volcaduras e inundaciones, un
ajuste suave por valor del vehículo y S/ 260 de grúa. El resultado va de S/ 246 a
S/ 17,647, con mediana en S/ 2,798. Un daño leve de dos piezas queda en unos S/ 857 y
un rayón de una pieza en S/ 353, que es el orden de magnitud real.

Sigue siendo un conjunto sintético: no reemplaza el historial de siniestros de una
aseguradora. En una implementación real se reentrenaría con sus datos y los umbrales se
recalcularían con esa distribución. La fórmula y los datos están en
`services/ml/training/`, así que el cálculo se puede reproducir y discutir.

## Los modelos no arrastran scikit-learn

El paquete con scikit-learn, numpy, scipy y pandas pesa 71 MB comprimido. Lambda
acepta 50. En vez de mover los modelos a un servidor, los bosques se exportaron a JSON
y se evalúan con la biblioteca estándar: el artefacto bajó a 2,4 MB y la predicción
tarda 0,2 ms. La paridad con scikit-learn se verificó sobre 500 casos, con una
diferencia máxima de medio céntimo.

El detalle que casi se escapa: scikit-learn recorre los árboles en `float32`. Si no se
replica ese redondeo, cinco de cada 250 árboles toman otra rama y el monto se desvía
un sol. Está documentado en [docs/arquitectura.md](docs/arquitectura.md).

## Interfaz

El asegurado entra con su número de póliza, sin registro: la aseguradora ya lo conoce
y pedirle una contraseña a alguien que acaba de chocar rompe la promesa de los tres
minutos. El analista sí entra con un código.

| Vista | Qué hace |
|---|---|
| Inicio | Reportar, consultar un caso por código o entrar al panel |
| Reportar | Chat con el agente, chips de datos y veredicto con monto y código |
| Seguimiento | Línea de tiempo del caso y la conversación completa |
| Panel | Cola por estado, detalle con evidencia y aprobación |

Hay capturas de escritorio y de móvil en [docs/capturas.md](docs/capturas.md).

## Poner esto a andar

Necesitas Node.js 22 o superior, Serverless Framework v4, credenciales de AWS Academy
y una clave de Groq. El camino corto:

```bash
cp .env.example .env    # completa las cinco variables
./scripts/deploy.sh ml
./scripts/deploy.sh core
./scripts/deploy.sh agente
./scripts/deploy.sh web
python3 seed/seed.py
```

El paso a paso, con lo que hay que revisar en la consola y los errores que ya nos
pasaron, está en [docs/runbook-despliegue.md](docs/runbook-despliegue.md).

## Pruebas

```bash
cd services/ml   && PYTHONPATH=. python3 -m unittest discover -s tests -v
cd services/core && PYTHONPATH=. python3 -m unittest discover -s tests -v
cd services/agente && PYTHONPATH=. python3 -m unittest discover -s tests -v
python3 -m unittest discover -s tests -v        # integración, sin AWS
```

La colección de Postman tiene 19 peticiones con pruebas automáticas y cubre el flujo
completo, incluidos los casos que deben fallar:
[docs/postman/](docs/postman/).

## Documentación

| Documento | Qué encontrarás |
|---|---|
| [docs/arquitectura.md](docs/arquitectura.md) | Servicios, flujo, modelo de datos y las decisiones técnicas que costaron más |
| [docs/runbook-despliegue.md](docs/runbook-despliegue.md) | Despliegue paso a paso, evidencias y los errores que ya nos pasaron |
| [docs/capturas.md](docs/capturas.md) | Capturas de escritorio y de móvil |
| [docs/postman/README.md](docs/postman/README.md) | Cómo importar y correr la colección de 19 peticiones |
| [docs/seguridad-dependencias.md](docs/seguridad-dependencias.md) | Qué dependencias llegan al navegador y por qué no se corre `npm audit fix --force` |
| [frontend/README.md](frontend/README.md) | Acceso, vistas y despliegue del frontend |
| [report/](report/) | Informe del proyecto: Partes A, B y C, en LaTeX y PDF |

## Autores

- Sebastian Rodrigo Garcia Villacorta
- Dante Guillermo Barreto Daza
- Clinton Michael Chulluncuy Reynoso
- Ronald Ramiro Hilario Orihuela
