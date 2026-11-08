# SiniestroExpress — Web

La parte visible del producto: el chat del asegurado y el panel del analista.

## Desarrollo local

Requiere **Node 20.19 o superior** (Vite 7 lo exige). Verifica con `node -v`.

```bash
npm install
cp .env.example .env      # completa las dos URL de API Gateway
npm run dev               # http://localhost:5173
```

Si faltan las variables, la app lo dice en pantalla en vez de inventar respuestas. No
hay modo demo a propósito: es fácil terminar presentando una interfaz que nunca habló
con la API.

## Despliegue en S3

```bash
export VITE_AGENTE_API=https://<api-agente>/dev
export VITE_CORE_API=https://<api-core>/dev
npm install
npx serverless deploy
```

El plugin `serverless-s3-sync` construye el bundle (`npm run build`) y lo publica en
el bucket al que apunta `WebsiteURL`.

## Acceso

- **Asegurado:** entra con su número de póliza. No hay registro: la aseguradora ya
  tiene sus datos y pedirle usuario y contraseña rompería la promesa de los tres
  minutos.
- **Analista:** código de demostración `ANALISTA-2026`, editable con
  `VITE_ANALISTA_CODE`. Se guarda en `sessionStorage`; es una barrera de piloto.
  Para producción correspondería Amazon Cognito con roles.

## Vistas

1. **Reportar siniestro** — identificarse con la póliza y conversar con el agente.
   Los chips muestran qué datos ya se recolectaron.
2. **Panel del ajustador** — cola por estado, detalle del expediente con la evidencia
   de los slots extraídos, aprobación o rechazo, y descarga del CSV.

## Identidad visual

Monocromo neutro con un solo acento naranja: fondo casi negro sin tinte, líneas finas,
etiquetas en mayúsculas con tracking amplio y titulares de display.
