FROM python:3.11-slim

WORKDIR /app

# Dependencias de sistema:
#  - build-essential / libpq-dev: compilar psycopg
#  - ffmpeg: requerido pelo OpenAI Whisper para decodificar o audio
#  - libpango/libharfbuzz/libgdk-pixbuf/libffi/libcairo + fonts-dejavu:
#    requeridos pelo WeasyPrint (skill gerar_documento_pdf) para renderizar
#    HTML+CSS -> PDF; as fontes DejaVu garantem acentuacao correta offline.
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    ffmpeg \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# PyTorch com CUDA 12.8 (cu128): necessario para a RTX 5090 (Blackwell / sm_120),
# que so e suportada a partir do torch 2.7.0. Instalado ANTES dos requirements
# para que transformers/sentence-transformers/whisper reaproveitem este build
# (e nao puxem o wheel default da PyPI). O wheel cu128 ja embute o runtime CUDA;
# o host so precisa do driver + nvidia-container-toolkit para o passthrough.
RUN pip install --no-cache-dir \
    torch>=2.7.0 \
    --index-url https://download.pytorch.org/whl/cu128

# Copiar apenas requirements primeiro para aproveitar o cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Baixar o modelo Whisper no build (cacheado em /root/.cache/whisper dentro da
# imagem) para que a primeira transcricao ja seja rapida, sem download em runtime.
ARG WHISPER_MODEL=medium
RUN python -c "import whisper; whisper.load_model('${WHISPER_MODEL}', device='cpu')"

# Copiar o código da aplicação e a lógica core
COPY . .

# Expor a porta que o FastAPI vai rodar
EXPOSE 8000

# Comando para iniciar o servidor
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
