#!/bin/bash

ollama serve &

sleep 5

ollama pull qwen3:4b

# pre loading the model
ollama run qwen3:4b "Say hello" --verbose

echo "Qwen3 is ready at http://localhost:11434"

wait
