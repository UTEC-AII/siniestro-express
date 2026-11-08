# Dependencias

Cada vez que se instala el frontend aparecen advertencias de deprecación y `npm audit`
cuenta entre cuatro y seis hallazgos. Ninguna de las dos cosas impide compilar ni
desplegar. Vale la pena entender por qué, porque la primera reacción es correr
`npm audit fix --force` y eso rompe el despliegue.

## Lo que llega al navegador y lo que no

De todas las dependencias, solo React viaja al usuario.

| Dependencia | Dónde se ejecuta | ¿Llega al navegador? |
|---|---|---|
| `react`, `react-dom` | Navegador | Sí |
| `vite`, `@vitejs/plugin-react` | Al compilar | No |
| `serverless`, `serverless-s3-sync` | Al desplegar | No |
| `aws-sdk` v2, `uuid`, `@auth0/s3` | Dentro del plugin de despliegue | No |

Los hallazgos que reporta `npm audit` son de herramientas de construcción. No viajan
al navegador ni se ejecutan en producción: viven en la máquina que despliega.

## Lo que sí arreglamos

`esbuild` (versión 0.24.2 o anterior) tenía un aviso moderado sobre el servidor de
desarrollo de Vite. Subimos a Vite 7 y al plugin de React 5. El build compila igual y
el paquete vulnerable desaparece del árbol. `npm audit` bajó de seis hallazgos a cuatro.

## Lo que queda y por qué lo dejamos

Los cuatro restantes vienen todos de la misma cadena: `serverless-s3-sync` usa
`@auth0/s3`, que a su vez usa `aws-sdk` v2 y `uuid`.

- `aws-sdk` v2 está descontinuado, pero aquí solo sube archivos a tu propio bucket.
  La región la fija el `serverless.yml`.
- `uuid` tiene un aviso que afecta a v3, v5 y v6. La aplicación no genera UUIDs: los
  identificadores salen de `uuid4` en Python.

Ninguno de los dos se puede aprovechar desde la aplicación publicada.

## Por qué no corremos `npm audit fix --force`

Lo que propone es retroceder `serverless-s3-sync` a la versión 1.7.3, que no entiende
la configuración actual, y saltar a otra versión mayor de Vite. Es decir: cambiar la
ruta de despliegue para resolver un aviso que no afecta al producto.

El riesgo real de `serverless-s3-sync` es otro: está marcado como no soportado. Si una
versión futura de Serverless lo rompe, la salida no es Node sino la consola de AWS:

```bash
npm run build
aws s3 sync dist/ s3://<bucket> --delete
```

Eso hace exactamente lo mismo que el plugin.
