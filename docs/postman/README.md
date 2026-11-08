# Colección de Postman

19 peticiones en cinco carpetas, ordenadas como se demuestra el flujo. Cada una
tiene pruebas automáticas, así que la corrida completa sirve como evidencia.

## Cómo usarla

1. Importar en Postman los dos archivos:
   - `SiniestroExpress.postman_collection.json`
   - `environment.example.json`
2. Seleccionar el entorno **SiniestroExpress — dev**.
3. Completar `core_url`, `agente_url` y `ml_url` con tus URL de API Gateway
   (incluye `/dev`).
4. Ejecutar **Run collection** de arriba hacia abajo, o petición por petición.

Las variables `chat_id`, `expediente_id` y `codigo` se llenan solas: las peticiones
tienen scripts que las guardan de la respuesta anterior.

Para ver el código de seguimiento: abre la consola de Postman (*View → Show Postman
Console*) y corre **Turno 2: cierra el caso**. Ahí se imprime
`codigo de seguimiento: SE-XXXXXX`. También queda en la pestaña *Variables* de la
colección y en el cuerpo de la respuesta.

## Qué demuestra cada carpeta

| Carpeta | Evidencia |
|---|---|
| 1. Modelos de ML | El bosque cargado sin dependencias, la severidad cambiando el monto y un `400` de validación |
| 2. Pólizas y expedientes | Consulta de póliza con deducible y `404` controlado |
| 3. Chat agéntico | Turno 1: un relato con tipo, ocho piezas y grúa; el agente extrae todo de una vez. Turno 2 cierra o confirma, sin duplicar el expediente |
| 4. Seguimiento y decisión | Consulta pública por código y el `409` que impide aprobar un caso rechazado |
| 5. Fotos y exportación | URL firmada, registro de las claves, listado de fotos y descarga del CSV |

## Para las capturas del informe

Cada petición trae pruebas automáticas, así que **Run collection** debe terminar en
verde. Esa pantalla, más tres o cuatro capturas de respuesta, es la evidencia de la
Parte C.

## Nota sobre la subida de fotos

`POST /fotos/presign` devuelve `upload_url`, que se guarda en la variable
`{{upload_url}}`. Para completar la subida en Postman: nueva petición `PUT` a esa
variable, pestaña **Body → binary**, elegir una imagen local. El `Content-Type` debe
ser el mismo que se pidió en el presign (`image/jpeg`, `image/png` o `image/webp`).
