FROM python:3.11 AS builder

WORKDIR /app

# install the CPU-only version of PyTorch
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

FROM python:3.11-slim

WORKDIR /app

RUN useradd --create-home appuser
USER appuser

ENV HF_HOME=/home/appuser/.cache/huggingface
RUN mkdir -p $HF_HOME

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

COPY --from=builder /usr/local/bin /usr/local/bin

COPY --from=builder /app .

EXPOSE 5000

ENV NAME="TranslationService"

CMD ["gunicorn", "-w", "3", "-k", "uvicorn.workers.UvicornWorker", "app:app", "--bind", "0.0.0.0:5000"]
