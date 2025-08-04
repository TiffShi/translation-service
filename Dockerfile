#--- Builder Stage ---
#use full python image which contains all necessary build tools
FROM python:3.11 AS builder

#set working directory in the container
WORKDIR /app

#install the CPU-only version of PyTorch
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

#--- Final Image ---
FROM python:3.11-slim

WORKDIR /app

RUN useradd --create-home appuser

ENV HF_HOME=/home/appuser/.cache/huggingface

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

COPY --from=builder /usr/local/bin /usr/local/bin

COPY --from=builder /app .

RUN chmod +x /app/entrypoint.sh

RUN mkdir -p $HF_HOME && chown -R appuser:appuser /app && chown -R appuser:appuser $HF_HOME

USER appuser

EXPOSE 5000

ENV NAME="TranslationService"

ENTRYPOINT ["/app/entrypoint.sh"]