# Despliegue

Guía para levantar el proyecto desde cero en una máquina de AWS Academy. Está escrita
con lo que nos fue pasando: si algo se rompe, lo más probable es que ya esté en la
última sección.

## 1. Antes de empezar

Necesitas, en la máquina de desarrollo:

- Node.js 20.19 o superior (`node -v`).
- Serverless Framework (`sudo npm install -g serverless`).
- Python 3 y `boto3` (`pip3 install boto3 --break-system-packages`).
- Las credenciales de AWS Academy del día.
- Una clave de Groq (`console.groq.com/keys`).

El repositorio:

```bash
cd /home/ubuntu
git clone https://github.com/UTEC-AII/siniestro-express.git
cd siniestro-express
```

Si la carpeta ya existía y solo quieres actualizarla, `git pull` basta. Cuando se queje
de cambios locales en `package-lock.json` o en algún `serverless.yml`, lo más rápido es
`git reset --hard origin/main`: tus datos viven en DynamoDB, no en archivos.

## 2. Credenciales y región

Las credenciales caducan cada cuatro horas. Antes de cada sesión:

```bash
cd ~/.aws && rm -f credentials && nano credentials
```

Pega el bloque de *AWS Details → Show*. Revisa que las dos líneas empiecen completas;
a veces se pierde la primera letra al pegar.

La región va aparte y se configura una sola vez:

```bash
aws configure set region us-east-1
```

Va en `~/.aws/config` y no en `credentials`, porque el archivo de credenciales lo
reescribes cada cuatro horas y te llevarías la región por delante. Los despliegues no
la necesitan (el `serverless.yml` ya la fija), pero los scripts que corren `boto3` sí.

## 3. Las variables

Los `serverless.yml` leen cuatro variables del entorno al empaquetar. Si falta una, el
despliegue se cae con un mensaje sobre `Cannot resolve '${env:...}'`, que no dice cuál
te falta.

Para no repetirlas en cada sesión, guárdalas en un `.env` (no se versiona):

```bash
cp .env.example .env
nano .env
```

```
GROQ_API_KEY=gsk_tu_clave
CORE_API_URL=https://xxxx.execute-api.us-east-1.amazonaws.com/dev
ML_API_URL=https://yyyy.execute-api.us-east-1.amazonaws.com/dev
VITE_AGENTE_API=https://xxxx.execute-api.us-east-1.amazonaws.com/dev
VITE_CORE_API=https://yyyy.execute-api.us-east-1.amazonaws.com/dev
```

Deja las URL vacías la primera vez. Las completas cuando cada servicio te devuelva la
suya.

### Si se cerró la sesión y perdiste las variables

Las URL no se pierden: cada stack las guarda como *Output*. Se ven en CloudFormation,
en la pestaña *Outputs* de `siniestro-ml-dev`, `siniestro-core-dev` y
`siniestro-agente-dev`, o en API Gateway, en la etapa `dev`.

Con esas tres se rearma el `.env` y se carga con:

```bash
set -a; . ./.env; set +a
```

## 4. Desplegar

El orden importa: cada servicio necesita la URL del anterior.

```bash
./scripts/deploy.sh ml
```

Copia la URL que imprime, hasta `/dev`, y pégala en `ML_API_URL`.

```bash
./scripts/deploy.sh core
```

Copia esa URL en `CORE_API_URL`. Este despliegue tarda unos minutos la primera vez
porque crea las tablas, sus índices y el bucket de fotos.

```bash
./scripts/deploy.sh agente
```

Solo entonces el chat puede funcionar.

Si prefieres hacerlo a mano, el script no es más que `npx serverless deploy` con las
variables verificadas antes.

## 5. Sembrar los datos

Las pólizas de prueba viven en `seed/polizas.json`. Se cargan así:

```bash
python3 seed/seed.py
```

Debería imprimir `20 polizas cargadas en siniestro-polizas-dev (us-east-1)`. El script
revisa que cada póliza traiga los quince campos y, si falta alguno, dice cuál y en cuál.

Si sale `ResourceNotFoundException`, la tabla todavía no existe: falta desplegar `core`.

## 6. Comprobar que responde

Cada servicio responde una ruta que los otros no tienen. Si perdiste el orden de las
URL, esto las identifica:

```bash
for B in https://aaa.execute-api.us-east-1.amazonaws.com/dev \
         https://bbb.execute-api.us-east-1.amazonaws.com/dev \
         https://ccc.execute-api.us-east-1.amazonaws.com/dev; do
  echo "$B"
  curl -s -o /dev/null -w "  health=%{http_code}" "$B/ml/health"
  curl -s -o /dev/null -w " polizas=%{http_code}" "$B/polizas/AUTO-2026-8801"
  curl -s -o /dev/null -w " chats=%{http_code}\n" "$B/chats"
done
```

La que responde `200` en `health` es `ml`, la del `200` en `polizas` es `core` y la del
`200` en `chats` es `agente`. Las otras rutas devuelven `403` con
`Missing Authentication Token`, que es lo normal.

Prueba el modelo con el mismo vehículo y tres severidades distintas:

```bash
for SEV in Leve Media Grave; do
  curl -s -X POST "$ML/ml/costo-reparacion" -H "Content-Type: application/json" \
    -d "{\"severidad\":\"$SEV\",\"antiguedad_vehiculo\":5,\"valor_vehiculo\":97000,
         \"tipo_siniestro\":\"Colision\",\"piezas_afectadas\":2,\"requiere_grua\":0,
         \"combustible\":\"Gasolina\"}"; echo
done
```

| Severidad | Monto aproximado | Ruta que sale |
|---|---|---|
| `Leve` | S/ 857 | `PAGO_EXPRES` |
| `Media` | S/ 1,790 | `AJUSTADOR` |
| `Grave` | S/ 5,904 | `PERITAJE` |

Es la misma colisión de dos piezas en el mismo auto. Lo único que cambia es el daño, y
la decisión cambia con él. Si con `Leve` te sale `AJUSTADOR`, revisa `ML_API_URL` en
`core`: probablemente quedó vacía.

Y el flujo completo:

```bash
curl -s -X POST "$CORE/expedientes" -H "Content-Type: application/json" -d '{
  "poliza_id": "AUTO-2026-8801",
  "slots": {"antiguedad_vehiculo": 5, "valor_vehiculo": 97000, "severidad": "Leve",
            "tipo_siniestro": "Colision", "piezas_afectadas": 2, "requiere_grua": 0,
            "combustible": "Gasolina"}}'
```

Debe devolver la ruta, el costo, el deducible, el monto a pagar y el código de
seguimiento.

## 7. El frontend

Necesita las dos URL de API antes de compilar, porque Vite las incrusta en el bundle.

```bash
./scripts/deploy.sh web
```

El despliegue no imprime la URL porque el stack solo crea un bucket. Se arma con el
nombre del bucket y la región:

```
http://siniestro-express-web-dev-<cuenta>.s3-website-us-east-1.amazonaws.com
```

O se consulta:

```bash
aws cloudformation describe-stacks --stack-name siniestro-web-dev \
  --query "Stacks[0].Outputs[].OutputValue" --output text --region us-east-1
```

Si al abrirla sale la franja roja de "API sin configurar", el build se hizo sin las
variables. Expórtalas y vuelve a desplegar; editar el `.env` no basta.

## 8. Qué revisar en la consola

| Servicio | Qué mirar |
|---|---|
| Lambda | 13 funciones: 3 de `siniestro-ml`, 6 de `siniestro-core`, 4 de `siniestro-agente`. En `sendMessage`, las variables `GROQ_API_KEY`, `CHAT_TABLE` y `CORE_API_URL` |
| API Gateway | Tres APIs, cada una con su etapa `dev` y CORS |
| DynamoDB | Las tres tablas. En expedientes, un ítem con `ruta`, `deducible`, `monto_indemnizable` y `codigo_seguimiento` |
| S3 | El bucket del frontend con *Static website hosting*, y el de fotos privado |
| CloudWatch | Los logs de `crearExpediente` cuando algo sale raro |

## 9. Evidencias

La colección de [docs/postman/](postman/) tiene 19 peticiones con pruebas automáticas.
Se importa, se elige el entorno y se corre de arriba abajo: las variables se encadenan
solas. La corrida en verde, más tres o cuatro capturas de respuesta, es la evidencia.

Vale la pena capturar también los casos que deben fallar: el `400` del enum inválido, el
`404` de una póliza que no existe y el `409` de intentar aprobar un caso rechazado.

## 10. Cuando algo falla

| Lo que ves | Qué pasó | Cómo se arregla |
|---|---|---|
| `The security token included in the request is expired` | Credenciales vencidas | Renovar `~/.aws/credentials` |
| `NoRegionError: You must specify a region` | Falta la región para `boto3` | `aws configure set region us-east-1` |
| `Cannot resolve '${env:...}'` | Falta una variable al empaquetar | Completar el `.env` y usar el script |
| `ResourceNotFoundException: Table ... not found` | La tabla no existe | Desplegar `core` antes de sembrar |
| La web dice "API sin configurar" | Se compiló sin las variables | Exportarlas y redesplegar |
| El chat responde `502` | Groq falló: clave, cuota o red | Ver el `detail` en la respuesta o en CloudWatch |
| `Groq respondio HTTP 401` | La clave no es válida | Crear otra y volver a desplegar `agente` |
| `Groq respondio HTTP 429` | Se agotó la cuota gratuita | Esperar o cambiar de clave |
| Todos los expedientes salen `PENDIENTE_PREDICCION` | `ML_API_URL` mal configurada en `core` | Corregirla y redesplegar |
| `Your local changes would be overwritten` | `npm install` tocó el lockfile | `git reset --hard origin/main` |

## 11. Limpiar y redesplegar

Antes de la exposición conviene dejar la cola sin casos de prueba:

```bash
python3 seed/reset.py                 # cuenta, no borra
python3 seed/reset.py --confirmar     # borra expedientes y chats
python3 seed/seed.py                  # repone las pólizas si hiciera falta
```

Y si cambias algo, esto dice qué mover:

| Si tocaste | Redesplega |
|---|---|
| `services/ml` o los modelos | `ml` |
| `services/core` | `core` |
| `services/agente` o el prompt | `agente` |
| `frontend` o las variables `VITE_*` | `web` |
| `seed/polizas.json` | nada: vuelve a correr `seed.py` |

Al terminar la exposición, para no gastar el crédito de la cuenta:

```bash
cd services/agente && npx serverless remove
cd ../core && npx serverless remove
cd ../ml && npx serverless remove
```

El borrado es por etapa. Y nunca uses el botón Reset de AWS Academy: se lleva por
delante todo lo que haya en la cuenta, sin confirmación.
