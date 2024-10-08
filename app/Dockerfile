FROM python:3.13-slim

LABEL build="JusteReseau - Version: ${RELEASE_TAG}"
LABEL org.opencontainers.image.description="This is a docker image for demonstrate and test some Kubernetes features."
LABEL org.opencontainers.image.licenses="WTFPL"
LABEL org.opencontainers.image.source="https://github.com/lucasmaurice/demo-app"
LABEL maintainer="JusteSonic"

ARG BUILD_VERSION
ARG BUILD_DATE

RUN mkdir /app
WORKDIR /app

COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app.py /app
COPY ./gunicorn.conf.py /app

RUN echo "${BUILD_VERSION}" >> /app/BUILD && echo "${BUILD_DATE}" >> /app/BUILD

EXPOSE 8080
CMD ["python", "-m" ,"gunicorn", "app:app"]
