#!/bin/bash

# Clean up Cassandra volumes for fresh start
echo "Cleaning up old Cassandra volumes..."
docker volume rm $(docker volume ls -q | grep -E "cassandra|db") 2>/dev/null || true

# Base image includes chromium and force x86_64 for Apple Silicon Macs
echo "Building base crawler image..."
docker build --platform linux/amd64 -f crawler/Dockerfile.crawler -t crawler-base .

# Builds services
echo "Building fetcher and watcher services..."
docker-compose build

echo "Build complete! Run 'docker-compose up' to start services."
