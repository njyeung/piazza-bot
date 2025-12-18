FROM ollama/ollama:latest

# Expose the Ollama API port
EXPOSE 11434

# Create a startup script that will pull the model and start serving
RUN mkdir -p /app
COPY llm/entrypoint.sh app/entrypoint.sh
RUN chmod +x app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
