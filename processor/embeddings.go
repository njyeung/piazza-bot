package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"sync"
)

// EmbeddingRequest represents a request to embed text
type EmbeddingRequest struct {
	Text     string
	Response chan EmbeddingResponse
}

// EmbeddingResponse represents the response from embedding
type EmbeddingResponse struct {
	Embedding []float32
	Error     error
}

// EmbeddingModel manages a long-lived Python embedding process
type EmbeddingModel struct {
	queue   chan EmbeddingRequest
	done    chan struct{}
	wg      sync.WaitGroup
	process *exec.Cmd
}

// LoadEmbeddingModel starts a long-lived Python embedding process
func InitEmbeddingModel() (*EmbeddingModel, error) {
	// Verify the script exists
	if _, err := os.Stat("embed.py"); err != nil {
		return nil, fmt.Errorf("embedding script not found at embed.py: %w", err)
	}

	// Start the Python process
	cmd := exec.Command("./venv/bin/python3", "embed.py")

	// Get pipes for stdin/stdout
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, fmt.Errorf("failed to create stdin pipe: %w", err)
	}

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, fmt.Errorf("failed to create stdout pipe: %w", err)
	}

	// Redirect stderr to our stderr
	cmd.Stderr = os.Stderr

	// Start the process
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("failed to start embedding process: %w", err)
	}

	em := &EmbeddingModel{
		queue:   make(chan EmbeddingRequest, 9999),
		done:    make(chan struct{}),
		process: cmd,
	}

	// Start the worker goroutine that handles the Python process
	em.wg.Add(1)
	go em.py_runtime_manager(stdin, stdout)

	return em, nil
}

// reads requests from the queue, sends them to Python, and returns responses
func (em *EmbeddingModel) py_runtime_manager(stdin io.WriteCloser, stdout io.ReadCloser) {
	defer em.wg.Done()

	stdinWriter := bufio.NewWriter(stdin)
	stdoutReader := bufio.NewScanner(stdout)

	for {
		select {
		case <-em.done:
			// Shutdown signal received
			stdin.Close()
			return
		case req := <-em.queue:
			// Send text to Python process
			_, err := stdinWriter.WriteString(req.Text + "\n")
			if err != nil {
				req.Response <- EmbeddingResponse{Error: fmt.Errorf("failed to write to Python: %w", err)}
				continue
			}

			err = stdinWriter.Flush()
			if err != nil {
				req.Response <- EmbeddingResponse{Error: fmt.Errorf("failed to flush: %w", err)}
				continue
			}

			// Read response from Python process
			if !stdoutReader.Scan() {
				req.Response <- EmbeddingResponse{Error: fmt.Errorf("failed to read from Python: %v", stdoutReader.Err())}
				continue
			}

			// Parse JSON embedding
			var embedding []float32
			err = json.Unmarshal(stdoutReader.Bytes(), &embedding)
			if err != nil {
				req.Response <- EmbeddingResponse{Error: fmt.Errorf("failed to parse embedding: %w", err)}
				continue
			}

			// Send response back
			req.Response <- EmbeddingResponse{Embedding: embedding}
		}
	}
}

// Generates an embedding for a single sentence
func (em *EmbeddingModel) EmbedSentence(text string) ([]float32, error) {
	respChan := make(chan EmbeddingResponse, 1)

	em.queue <- EmbeddingRequest{
		Text:     text,
		Response: respChan,
	}

	resp := <-respChan
	return resp.Embedding, resp.Error
}

// Helper to call EnbedSentence multiple times
func (em *EmbeddingModel) EmbedSentences(texts []string) ([][]float32, error) {
	if len(texts) == 0 {
		return [][]float32{}, nil
	}

	result := make([][]float32, len(texts))
	for i, text := range texts {
		embedding, err := em.EmbedSentence(text)
		if err != nil {
			return nil, fmt.Errorf("failed to embed sentence %d: %w", i, err)
		}
		result[i] = embedding
	}

	return result, nil
}

// Shut down the embedding process gracefully
func (em *EmbeddingModel) Close() error {
	close(em.done)

	em.wg.Wait()

	// Wait for the Python proc to exit
	err := em.process.Wait()
	if err != nil && err.Error() != "signal: terminated" {
		return fmt.Errorf("Python process error: %w", err)
	}

	return nil
}
