FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./src ./src

RUN useradd -r medimg && \
    mkdir -p /var/lib/medimg-sync/inbox /var/lib/medimg-sync/archive /var/lib/medimg-sync/quarantine && \
    chown -R medimg:medimg /var/lib/medimg-sync

USER medimg

CMD ["python", "-m", "src.main"]
