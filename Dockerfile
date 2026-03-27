FROM dailyco/pipecat-base:latest

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copiar archivos de dependencias
COPY pyproject.toml uv.lock ./

# Instalar dependencias (sin mounts)
RUN uv sync --locked --no-dev

# Copiar el código
COPY . .

EXPOSE 7860

CMD ["uv", "run", "python", "bot.py"]