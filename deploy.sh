#!/bin/bash

BUILD_DATE=$(date +"%Y-%m-%d@%H:%M:%S")
BUILD_VERSION=$(date +"%Y-%m-%d@%H:%M:%S" | sha256sum | head -c 10)

docker build \
  --build-arg BUILD_DATE=$BUILD_DATE \
  --build-arg BUILD_VERSION=$BUILD_VERSION \
  --tag ghcr.io/lucasmaurice/kube_demo_1:latest \
  --tag ghcr.io/lucasmaurice/kube_demo_1:$BUILD_VERSION \
  app

docker push ghcr.io/lucasmaurice/kube_demo_1:$BUILD_VERSION
docker push ghcr.io/lucasmaurice/kube_demo_1:latest
kubectl set image deployment/demo-app app=ghcr.io/lucasmaurice/kube_demo_1:$BUILD_VERSION -n demo-app
