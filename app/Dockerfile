FROM python:3.12-slim

ARG BUILD_VERSION
ARG BUILD_DATE

RUN mkdir /app
WORKDIR /app

COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app.py /app/app.py

RUN echo "${BUILD_VERSION}" >> /app/BUILD && echo "${BUILD_DATE}" >> /app/BUILD

EXPOSE 8080
CMD ["python", "app.py"]
