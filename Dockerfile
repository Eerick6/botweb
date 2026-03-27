# Imagen base compatible con Railway
FROM python:3.11-slim

# Evita problemas de logs y buffers
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv (gestor de dependencias rápido)
RUN pip install --no-cache-dir uv

# Copiar archivos de dependencias primero (cache Docker)
COPY pyproject.toml uv.lock ./

# Instalar dependencias del proyecto
RUN uv sync --locked --no-dev

# Copiar el resto del código
COPY . .

# Puerto requerido por Railway
EXPOSE 7860

# Variable de puerto (Railway la inyecta automáticamente)
ENV PORT=7860

# Comando de inicio
CMD ["uv", "run", "python", "bot.py"]