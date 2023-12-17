FROM bitnami/python:3.10
WORKDIR /app
# Update the package list and install necessary packages including GDAL and Cairo
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        libcairo2 \
    && rm -rf /var/lib/apt/lists/*
# Set environment variables so that Python package installer can find gdal-config
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
# Copy necessary files
COPY requirements.txt ./
# Upgrade pip and install dependencies from requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt
# Copy project files into the container
COPY *.py .
COPY handlers /app/handlers
# Command to run the application, using the TELEGRAM_BOT_TOKEN environment variable
CMD python tg.py ${TELEGRAM_BOT_TOKEN}
