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
# onboard.py ships too: docker-compose.yml documents
# `docker compose exec -it vaultex python3 setup/onboard.py` as the Path B way to
# map the taxonomy, and it needs write_policy.example.md to seed the vault's
# write_policy.md. install_ui.py comes with it -- onboard.py draws the same
# selector install.py does, and that runs in here, not on the host. (Mode is
# not set here: it's VAULTEX_MODE in .env, chosen by install.py.)
COPY server.py index_vault.py write_policy.example.md ./
COPY setup/onboard.py setup/install_ui.py setup/

CMD ["python3", "server.py"]
