FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

# Install deps
RUN apt-get update && apt-get install -y \
    wget \
    git \
    build-essential \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Go
RUN wget -q https://go.dev/dl/go1.21.0.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz && \
    rm go1.21.0.linux-amd64.tar.gz

ENV PATH=/usr/local/go/bin:$PATH

# Install ONNX Runtime C/C++ library **v1.23.2**
RUN mkdir -p /tmp/onnxrt && \
    cd /tmp/onnxrt && \
    wget -q https://github.com/microsoft/onnxruntime/releases/download/v1.23.2/onnxruntime-linux-x64-1.23.2.tgz && \
    tar -xzf onnxruntime-linux-x64-1.23.2.tgz && \
    cd onnxruntime-linux-x64-1.23.2 && \
    cp -r include/* /usr/local/include/ && \
    cp -r lib/* /usr/local/lib/ && \
    ldconfig && \
    cd / && \
    rm -rf /tmp/onnxrt

# Make sure loader can find libonnxruntime.so
ENV LIBRARY_PATH=/usr/local/lib:$LIBRARY_PATH
ENV LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH

# Optional but explicit
ENV CGO_ENABLED=1

WORKDIR /app

# Copy go module files first to leverage Docker cache
COPY go.mod go.sum ./
RUN go mod download

# Copy the rest of the source
COPY . .

# Build the binary instead of go run at container start
RUN go build -o app ./test_embedding.go

CMD ["./app"]
