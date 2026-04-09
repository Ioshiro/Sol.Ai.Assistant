# Test Integrazione

Stack di test per Sol AI + Pipecat + Langfuse.

## Componenti

- `SolAI.Pipecat.LLMService`: API ASP.NET Core OpenAI-compatible
- `bot.py`: bot Pipecat CPU
- `bot_cuda.py`: bot Pipecat GPU
- `bot_xtts.py`: bot Pipecat con XTTS
- `chat_openai_console.py`: client console OpenAI-compatible
- `docker-compose.yml`: stack locale completo con Langfuse, Ollama, service .NET, XTTS e proxy HTTPS

## Avvio rapido dello stack completo

Prerequisiti:
- Docker Desktop / Docker Engine

Avvio:

```bash
docker compose up --build
```

Servizi esposti localmente via HTTP:
- Langfuse UI: `http://localhost:3000`
- Langfuse OTLP ingest: `http://localhost:3000/api/public/otel`
- Sol AI LLM Service: `http://localhost:5077`
- Ollama: `http://localhost:11434`
- XTTS: `http://localhost:8000`

Servizi esposti via HTTPS dal proxy Caddy:
- Bot UI: `https://localhost:8443/client`
- Langfuse UI: `https://localhost:9443`
- Sol AI LLM Service: `https://localhost:9543`
- XTTS: `https://localhost:9643`

Se vuoi usare il bot da un altro PC in LAN:
- imposta `HTTPS_HOST` nella tua `.env` sul LAN IP o su un hostname raggiungibile
- avvia il bot con `python bot.py --host 0.0.0.0 --port 7860`
- apri `https://<HTTPS_HOST>:8443/client`

Il primo avvio può richiedere tempo perché:
- Langfuse inizializza il proprio stack (Postgres, ClickHouse, Redis, MinIO)
- `ollama-pull` scarica il modello definito in `OLLAMA_MODEL`

### Configurazione centralizzata delle chiavi Langfuse

- copia `.env.example` in `.env`
- inserisci lì `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
- `docker compose` legge automaticamente `.env`
- il helper Python legge automaticamente `.env` se lanci i bot fuori da Docker

### HTTPS locale

Il proxy HTTPS usa Caddy con `tls internal`.
- La prima volta potresti vedere un avviso del browser finché non accetti o non ti fidi della CA locale di Caddy.
- Su LAN, per un'esperienza pulita, usa un hostname/IP stabile in `HTTPS_HOST`.

## Avvio del servizio .NET in locale

```bash
dotnet run --project SolAI.Pipecat.LLMService/SolAI.Pipecat.LLMService.csproj
```

Endpoint principali:
- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`

Request sample:
- `SolAI.Pipecat.LLMService/SolAI.Pipecat.LLMService.http`

## Uso dei bot Pipecat

Prima di eseguire i bot, installa i package runtime e di tracing:

```bash
pip install -r requirements-bots.txt
```

I bot usano tracing Langfuse OTLP tramite `langfuse_observability.py`.

### Bot CPU

```bash
python bot.py
```

### Bot GPU

```bash
python bot_cuda.py
```

### Bot con XTTS

```bash
python bot_xtts.py
```

Per `bot_xtts.py` puoi configurare:
- `XTTS_BASE_URL` (default `http://localhost:8000`)
- `XTTS_VOICE_ID` (default `Ana Florence`)

## Client console

```bash
python chat_openai_console.py --base-url http://localhost:5077 --api-key test-key
```

Comandi utili nella console:
- `/help`
- `/models`
- `/model [nome]`
- `/system [testo]`
- `/stream on|off`
- `/toolchoice auto|required|none`
- `/reset`
- `/history`
- `/exit`

## Note operative

- `bot.py` usa Whisper `medium` su CPU e Kokoro TTS
- `bot_cuda.py` usa Whisper `large-v3-turbo` su CUDA e Kokoro TTS
- `bot_xtts.py` usa Whisper `large-v3-turbo` e XTTS
- XTTS nel compose corrente usa l'immagine CPU compatibile; se vuoi una variante GPU devi aggiungere un override dedicato
- Langfuse è self-hosted e inizializzato con chiavi demo locali nel compose
- `SolAI.Pipecat.LLMService` esporta trace OpenTelemetry/OTLP direttamente su Langfuse
- Se `python bot.py` fallisce con moduli mancanti, installa prima l'ambiente Python del progetto usando `requirements-bots.txt`

## File utili

- `docker-compose.yml`
- `Caddyfile`
- `langfuse_observability.py`
- `requirements-bots.txt`
- `requirements-observability.txt`
- `STATO_LAVORO.md`
