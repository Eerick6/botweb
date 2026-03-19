from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import TextFrame


class StreamingLLMProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.buffer = ""
        self.started = False

    async def process_frame(self, frame, direction):
        # ✅ Esperar StartFrame (CRÍTICO)
        if not self.started:
            if frame.__class__.__name__ == "StartFrame":
                self.started = True
            await self.push_frame(frame)
            return

        # ✅ Solo procesar texto del LLM
        if isinstance(frame, TextFrame):
            self.buffer += frame.text

            if self.should_flush(self.buffer):
                await self.push_frame(TextFrame(self.clean_text(self.buffer)))
                self.buffer = ""
            return

        # ✅ Pasar todo lo demás (audio, control, etc)
        await self.push_frame(frame)

    def should_flush(self, text: str) -> bool:
        text = text.strip()

        # 🔥 evita frases muy cortas
        if len(text) < 40:
            return False

        # 🔥 corta en final de frase natural
        if text.endswith((".", "?", "!")):
            return True

        return False

    def clean_text(self, text: str) -> str:
        return text.strip()