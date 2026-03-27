# Imagen base
FROM python:3.11-slim

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    git \
    build-essential \
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
RUN pip install --no-cache-dir uv

# Copiar solo pyproject (NO uv.lock)
COPY pyproject.toml ./

# Instalar dependencias SIN lock (clave para evitar error)
RUN uv sync --no-dev --system

# Copiar el resto del proyecto
COPY . .

# Puerto para Railway
ENV PORT=7860
EXPOSE 7860

# Comando de inicio
CMD ["python", "bot.py"]