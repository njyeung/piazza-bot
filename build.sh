#!/bin/bash

# Use BuildKit if availbale
export DOCKER_BUILDKIT=1

# Stop and remove all containers first
docker compose down 2>/dev/null || true

# Clean up Cassandra volumes for fresh start
docker volume rm $(docker volume ls -q | grep -E "cassandra|db") 2>/dev/null || true

# Clean up Kafka volumes for fresh start
docker volume rm $(docker volume ls -q | grep -E "piazza_kafka-data") 2>/dev/null || true

# Base image includes chromium and force x86_64 for Apple Silicon Macs
docker build --platform linux/amd64 -f crawler/Dockerfile.crawler -t crawler-base .

# Builds services
docker-compose build

echo "Build complete! Run 'docker-compose up' to start services."
