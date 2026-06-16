FROM python:3.12-slim

WORKDIR /app

# Use Tsinghua mirror for Debian apt packages (faster from Asia)
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g; s|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        curl \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Use Tsinghua mirror for pip (faster from Asia)
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 300 --retries 10 -r requirements.txt

# Playwright's bundled Chromium + its OS deps (no system Edge/Chrome on Linux).
# render_cards.py picks this up via RENDER_BROWSER_CHANNEL=chromium below.
RUN playwright install --with-deps chromium

COPY *.py ./
COPY templates/ ./templates/

ENV RENDER_BROWSER_CHANNEL=chromium

RUN mkdir -p /app/data /app/logs /app/data/cards

CMD ["python", "main.py"]
