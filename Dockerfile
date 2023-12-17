FROM bitnami/python:3.10
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        libcairo2 \
    && rm -rf /var/lib/apt/lists/*
# 设置环境变量，使得 Python 包安装程序可以找到 gdal-config
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
# Copy necessary files
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt
# 复制项目文件到容器中
COPY *.py .
COPY handlers /app/handlers
ENV GOOGLE_GEMINI_KEY=your_google_gemini_apikey
CMD python tg.py ${TELEGRAM_BOT_TOKEN}
