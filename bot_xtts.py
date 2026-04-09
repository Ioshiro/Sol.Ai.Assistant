import os
from langfuse_observability import configure_pipecat_langfuse
configure_pipecat_langfuse("bot-xtts")


import aiohttp
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.observers.loggers.metrics_log_observer import MetricsLogObserver
from pipecat.observers.startup_timing_observer import StartupTimingObserver
from pipecat.observers.user_bot_latency_observer import UserBotLatencyObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIProcessor
from pipecat.runner.types import RunnerArguments
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.base_llm import OpenAILLMSettings
from pipecat.services.whisper.stt import WhisperSTTService, WhisperSTTSettings
from pipecat.services.xtts.tts import XTTSService
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport


LMSTUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
#LMSTUDIO_MODEL = "qwen3.5-4b"  # <-- cambia col tuo model id
#LMSTUDIO_MODEL = "gpt-oss-20b"
#LMSTUDIO_MODEL = "gemma-3-4b-it"
#LMSTUDIO_MODEL = "llama-3.2-3b-instruct"
LMSTUDIO_MODEL = "gemma4:e4b"
WHISPER_MODEL = "large-v3-turbo"
XTTS_BASE_URL = os.getenv("XTTS_BASE_URL", "http://localhost:8000")
XTTS_VOICE_ID = os.getenv("XTTS_VOICE_ID", "Ana Florence")

#Claribel Dervla
#Sofia Hellen
#Ana Florence
#Annmarie Neleà
#Andrew Chipper
#Viktor Eka
#Luis Moray
#Marcos Rudaski

def create_observers():
    metrics_observer = MetricsLogObserver()
    startup_observer = StartupTimingObserver()
    latency_observer = UserBotLatencyObserver()
    latency_state = {"user_to_bot": None}

    @startup_observer.event_handler("on_startup_timing_report")
    async def on_startup_timing_report(observer, report):
        logger.info(
            f"Pipeline startup completed in {report.total_duration_secs:.3f}s"
        )
        for timing in report.processor_timings:
            logger.info(
                "Startup timing | "
                f"processor={timing.processor_name} "
                f"offset={timing.start_offset_secs:.3f}s "
                f"duration={timing.duration_secs:.3f}s"
            )

    @startup_observer.event_handler("on_transport_timing_report")
    async def on_transport_timing_report(observer, report):
        if report.bot_connected_secs is not None:
            logger.info(
                f"Transport timing | bot_connected={report.bot_connected_secs:.3f}s"
            )
        if report.client_connected_secs is not None:
            logger.info(
                f"Transport timing | client_connected={report.client_connected_secs:.3f}s"
            )

    @latency_observer.event_handler("on_first_bot_speech_latency")
    async def on_first_bot_speech_latency(observer, latency_seconds):
        logger.info(f"Latency | first_bot_speech={latency_seconds:.3f}s")

    @latency_observer.event_handler("on_latency_measured")
    async def on_latency_measured(observer, latency_seconds):
        latency_state["user_to_bot"] = latency_seconds
        logger.info(f"Latency | user_to_bot={latency_seconds:.3f}s")

    @latency_observer.event_handler("on_latency_breakdown")
    async def on_latency_breakdown(observer, breakdown):
        if breakdown.user_turn_secs is not None:
            logger.info(f"Latency breakdown | user_turn={breakdown.user_turn_secs:.3f}s")

        for item in breakdown.ttfb:
            model = f" model={item.model}" if item.model else ""
            logger.info(
                "Latency breakdown | "
                f"processor={item.processor}{model} "
                f"ttfb={item.duration_secs:.3f}s"
            )

        if breakdown.text_aggregation is not None:
            logger.info(
                "Latency breakdown | "
                f"processor={breakdown.text_aggregation.processor} "
                f"text_aggregation={breakdown.text_aggregation.duration_secs:.3f}s"
            )

        for item in breakdown.function_calls:
            logger.info(
                "Latency breakdown | "
                f"function={item.function_name} duration={item.duration_secs:.3f}s"
            )

        chronological_events = breakdown.chronological_events()
        if chronological_events:
            logger.info("Latency timeline | " + " | ".join(chronological_events))

        total_ttfb = sum(item.duration_secs for item in breakdown.ttfb)
        summary_parts = []
        user_to_bot = latency_state.get("user_to_bot")
        if user_to_bot is not None:
            summary_parts.append(f"user_wait={user_to_bot:.3f}s")
        if breakdown.user_turn_secs is not None:
            summary_parts.append(f"user_turn={breakdown.user_turn_secs:.3f}s")
        if breakdown.ttfb:
            summary_parts.append(f"service_ttfb_total={total_ttfb:.3f}s")
            summary_parts.extend(
                f"{item.processor}={item.duration_secs:.3f}s" for item in breakdown.ttfb
            )
        if breakdown.text_aggregation is not None:
            summary_parts.append(
                f"text_aggregation={breakdown.text_aggregation.duration_secs:.3f}s"
            )
        if breakdown.function_calls:
            summary_parts.append(
                "functions="
                + ", ".join(
                    f"{item.function_name}:{item.duration_secs:.3f}s"
                    for item in breakdown.function_calls
                )
            )
        if breakdown.user_turn_secs is not None or breakdown.ttfb:
            total_turn = (breakdown.user_turn_secs or 0.0) + total_ttfb
            if breakdown.text_aggregation is not None:
                total_turn += breakdown.text_aggregation.duration_secs
            summary_parts.append(f"turn_total_estimate={total_turn:.3f}s")
        if summary_parts:
            logger.info("Turn summary | " + " | ".join(summary_parts))
        latency_state["user_to_bot"] = None

    return [metrics_observer, startup_observer, latency_observer]


async def run_bot(transport):
    logger.info("Creating Whisper STT...")
    stt = WhisperSTTService(
        settings=WhisperSTTSettings(
            model=WHISPER_MODEL,
            language=Language.IT,
            no_speech_prob=0.5,
        ),
        device="cuda",
        compute_type="float16",
    )

    logger.info("Creating Sol AI LLM service...")
    llm = OpenAILLMService(
        api_key="lm-studio",
        base_url=LMSTUDIO_BASE_URL,
        settings=OpenAILLMSettings(
            model=LMSTUDIO_MODEL,
        ),
    )

    async with aiohttp.ClientSession() as session:
        logger.info("Creating XTTS TTS...")
        logger.info(f"XTTS server: {XTTS_BASE_URL} | voice: {XTTS_VOICE_ID}")
        tts = XTTSService(
            aiohttp_session=session,
            base_url=XTTS_BASE_URL,
            voice_id=XTTS_VOICE_ID,
            language=Language.IT,
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "Sei un assistente vocale in italiano. "
                    "Rispondi in modo breve, chiaro e naturale. "
                    "Usa solo testo, non emoticons, simboli o formattazione particolare."
                    "Evita elenchi lunghi. "
                    "Se l'input dell'utente e' poco chiaro, chiedi una sola breve chiarificazione."
                ),
            }
        ]

        context = LLMContext(messages)
        context_aggregator = LLMContextAggregatorPair(
            context,
            user_params=LLMUserAggregatorParams(
                vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.3))
            ),
        )

        rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

        pipeline = Pipeline(
            [
                transport.input(),
                stt,
                context_aggregator.user(),
                rtvi,
                llm,
                tts,
                transport.output(),
                context_aggregator.assistant(),
            ]
        )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            enable_tracing=True,
            observers=create_observers(),
        )

        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info(f"Client connected: {client}")
            await task.queue_frame(TTSSpeakFrame("Ciao, come posso aiutarti?"))

        runner = PipelineRunner(handle_sigint=False)
        await runner.run(task)


async def bot(runner_args: RunnerArguments):
    transport = SmallWebRTCTransport(
        webrtc_connection=runner_args.webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    )

    await run_bot(transport)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
