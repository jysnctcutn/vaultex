FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
# torch is a transitive dep of sentence-transformers; on Linux pip defaults
# to the CUDA build (~3.5GB of unused nvidia/triton packages) since this
# app is CPU-only. Install the CPU wheel first so the later install is a
# no-op for torch.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

COPY core/ core/
COPY server.py index_vault.py ./

CMD ["python3", "server.py"]
