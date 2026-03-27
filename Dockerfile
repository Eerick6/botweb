FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb-cursor0 \
    libxcb-shape0 \
    libxcb-xfixes0 \
    libxcb-icccm4 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv
RUN pip install uv

WORKDIR /app

# Copiar dependencias
COPY pyproject.toml uv.lock ./

# Instalar dependencias Python
RUN uv sync --locked --no-dev

# Copiar código
COPY . .

EXPOSE 7860

CMD ["uv", "run", "python", "bot.py"]