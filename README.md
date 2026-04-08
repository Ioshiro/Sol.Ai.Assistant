# Test Integrazione

Stack di test per Sol AI + Pipecat + Langfuse.

## Componenti

- `SolAI.Pipecat.LLMService`: API ASP.NET Core OpenAI-compatible
- `bot.py`: bot Pipecat CPU
- `bot_cuda.py`: bot Pipecat GPU
- `bot_xtts.py`: bot Pipecat con XTTS
- `chat_openai_console.py`: client console OpenAI-compatible
- `docker-compose.yml`: stack locale completo con Langfuse, Ollama, service .NET e XTTS

## Avvio rapido dello stack completo

Prerequisiti:
- Docker Desktop / Docker Engine
- NVIDIA GPU driver se vuoi usare il servizio XTTS così com'è

Avvio:

```bash
docker compose up --build
```

Servizi esposti localmente:
- Langfuse UI: `http://localhost:3000`
- Langfuse OTLP ingest: `http://localhost:3000/api/public/otel`
- Sol AI LLM Service: `http://localhost:5077`
- Ollama: `http://localhost:11434`
- XTTS: `http://localhost:8000`

Il primo avvio può richiedere tempo perché:
- Langfuse inizializza il proprio stack (Postgres, ClickHouse, Redis, MinIO)
- `ollama-pull` scarica il modello definito in `OLLAMA_MODEL`

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

Prima di eseguire i bot, installa i package di tracing:

```bash
pip install -r requirements-observability.txt
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
- XTTS nel compose corrente richiede GPU NVIDIA
- Langfuse è self-hosted e inizializzato con chiavi demo locali nel compose
- `SolAI.Pipecat.LLMService` esporta trace OpenTelemetry/OTLP direttamente su Langfuse


## File utili

- `docker-compose.yml`
- `langfuse_observability.py`
- `requirements-observability.txt`
- `STATO_LAVORO.md`
