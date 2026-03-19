#
# Copyright (c) 2024-2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Pipecat TaxiBlau Web Bot (Optimizado)."""

import os

from dotenv import load_dotenv
from loguru import logger

print("🚀 Starting TaxiBlau Web Bot...")
print("⏳ Loading models and imports (20 seconds, first run only)\n")

logger.info("Loading Silero VAD model...")
from pipecat.audio.vad.silero import SileroVADAnalyzer

logger.info("✅ Silero VAD model loaded")

from deepgram import LiveOptions
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.cartesia.tts import CartesiaTTSService, GenerationConfig
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyParams

# Tools
from tools import register_tools
from api_client import CallsAPIClient

logger.info("✅ All components loaded successfully!")

load_dotenv(override=True)


# 🔥 PROMPT OPTIMIZADO (MENOS TOKENS = MENOS DELAY)
SYSTEM_PROMPT = """
Eres una operadora virtual de TaxiBlau.

Reglas:
- Español, tono profesional, frases cortas
- Hora de referencia: Madrid
- Si no dicen hora: asumir "ahora"

Flujo:

1. Pedir teléfono SIEMPRE primero
2. Con teléfono → check_user_status(phone)

Si existe:
- Saluda por nombre y pregunta en qué ayudar

Si no existe:
- Pedir nombre → register_user(phone, name)
- Continuar

Para reservas:
- Validar recogida con resolve_address
- Validar destino con resolve_address
- Pedir fecha/hora si falta
- Confirmar antes de crear
- Luego create_taxi_service

Reglas críticas:
- No aceptar direcciones fuera de España
- No inventar datos
- No avanzar sin teléfono

Instrucciones de interpretación de números de teléfono:

- El usuario puede decir números usando palabras, combinando unidades, decenas, centenas o miles.
- Debes **convertir todo a dígitos concatenados**, respetando el orden exacto.
- Ejemplos:
  - "cero nueve seis noventa cincuenta tres seis seis" → `0969050366`
  - "uno dos treinta y cuatro cinco seis siete" → `1234567`
  - "noventa y ocho ciento veintitrés cuatro cinco" → `9812345`
- No sumar ni transformar los números a palabras.
- Siempre entregar el número **solo en dígitos**, sin espacios, guiones ni caracteres extra.
- Si no entiendes, pide que repita el número palabra por palabra.
"""

async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    logger.info("🚀 Starting TaxiBlau Web Bot")

    # 🔥 STT (rápido y correcto)
    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        live_options=LiveOptions(
            model="nova-3-general",
            language="es",
            smart_format=False,
        ),
    )

    # 🔥 TTS optimizado (menos fragmentación)
    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id="d4db5fb9-f44b-4bd1-85fa-192e0f0d75f9",
        params=CartesiaTTSService.InputParams(
            language="es",
            generation_config=GenerationConfig(
                emotion="friendly",
                speed=1.2,
                # 👇 ayuda a evitar respuestas cortadas
                chunk_size=200,
            ),
        ),
    )

    # 🔥 LLM OPTIMIZADO (AQUÍ ESTÁ LA MAGIA)
    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4o-mini",  # ⚡ rápido
        stream=True,          # ⚡ streaming real
    )

    backend_url = os.getenv("BACKEND_URL", "http://localhost:3000")

    # Calls API
    calls_client = CallsAPIClient(backend_url)

    await calls_client.register_call()
    logger.info(f"📞 Llamada registrada: {calls_client.current_call_sid}")

    # Tools
    tools_schema = register_tools(
        llm=llm,
        backend_url=backend_url,
        calls_client=calls_client,
    )

    logger.info(f"✅ Tools registered with backend: {backend_url}")

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
    ]

    context = LLMContext(
        messages=messages,
        tools=tools_schema,
    )

    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer()
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    # 🔥 EVENTO CONEXIÓN
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("✅ Client connected")

        context.add_message(
            {
                "role": "system",
                "content": (
                    "Cliente conectado. Saluda con "
                    "'¡Bienvenido a TaxiBlau! Soy tu asistente virtual.' "
                    "y pide su teléfono inmediatamente."
                ),
            }
        )

        await task.queue_frames([LLMRunFrame()])

    # 🔥 EVENTO DESCONEXIÓN
    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("❌ Client disconnected")
        await calls_client.complete_call()
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)


async def bot(runner_args: RunnerArguments):
    """Main bot entry point"""

    transport_params = {
        "daily": lambda: DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    }

    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main
    main()