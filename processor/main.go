package main

import (
	"fmt"
	"log"
	"os"
)

func main() {
	config := LoadCassandraConfig()
	embeddingConfig := DefaultEmbeddingConfig()

	// Load embedding model (includes tokenizer)
	embeddingModel, err := InitEmbeddingModel(embeddingConfig)
	if err != nil {
		log.Fatalf("Failed to load embedding model: %v", err)
	}
	defer embeddingModel.Close()

	// Connect to Cassandra
	session, err := ConnectCassandra(config)
	if err != nil {
		log.Fatalf("Failed to connect to Cassandra: %v", err)
	}
	defer session.Close()

	// Fetch first available transcript
	transcript, err := FetchFirstTranscript(session)
	if err != nil {
		log.Fatalf("Failed to fetch transcript: %v", err)
	}

	// Parse SRT into frames
	frames := ParseSRT(transcript.TranscriptText)

	// Extract sentences from frames
	sentences := embeddingModel.ExtractSentencesFromFrames(frames)

	// Embed sentences (need pointers since it modifies the struct)
	sentencePtrs := make([]*Sentence, len(sentences))
	for i := range sentences {
		sentencePtrs[i] = &sentences[i]
	}
	err = embeddingModel.EmbedSentences(sentencePtrs)
	if err != nil {
		log.Fatalf("Failed to embed sentences: %v", err)
	}

	// Perform semantic chunking with default config
	chunkingCfg := DefaultChunkingConfig()
	chunks := chunkingCfg.ExtractChunksFromSentences(sentences)

	// Finally, embed chunks
	chunkPtrs := make([]*Chunk, len(chunks))
	for i := range chunks {
		chunkPtrs[i] = &chunks[i]
	}
	err = embeddingModel.EmbedChunks(chunkPtrs)
	if err != nil {
		log.Fatalf("Failed to finalize chunk embeddings: %v", err)
	}

	// Write chunks to file
	fmt.Println("Writing chunks to disk...")
	err = WriteChunksToFile(chunks, "chunks_output.txt")
	if err != nil {
		log.Fatalf("Failed to write chunks to file: %v", err)
	}
	fmt.Println("Chunks written to chunks_output.txt")
}

// WriteChunksToFile writes all chunks to a file with detailed information
func WriteChunksToFile(chunks []Chunk, filename string) error {
	file, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer file.Close()

	for i, chunk := range chunks {
		fmt.Fprintf(file, "===== CHUNK %d =====\n", i)
		fmt.Fprintf(file, "Start Time: %s\n", chunk.StartTime)
		fmt.Fprintf(file, "Sentences: %d\n", chunk.NumSentences)
		fmt.Fprintf(file, "Token Count: %d\n", chunk.TokenCount)
		fmt.Fprintf(file, "\n--- TEXT ---\n")
		fmt.Fprintf(file, "%s\n", chunk.Text)
		fmt.Fprintf(file, "\n\n")
	}

	return nil
}
