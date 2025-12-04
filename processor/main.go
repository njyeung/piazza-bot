package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
)

func main() {
	config := LoadConfig()

	// Load tokenizer
	tokenizerPath := filepath.Join(".", "..", "embedding", "tokenizer.json")
	err := InitTokenizer(tokenizerPath)
	if err != nil {
		log.Fatalf("Failed to load tokenizer: %v", err)
	}

	// Load embedding model
	embeddingModel, err := InitEmbeddingModel()
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

	fmt.Printf("Processing transcript:\n")
	fmt.Printf("  Class: %s\n", transcript.ClassName)
	fmt.Printf("  Professor: %s\n", transcript.Professor)
	fmt.Printf("  Semester: %s\n", transcript.Semester)
	fmt.Printf("  Title: %s\n", transcript.LectureTitle)
	fmt.Printf("  URL: %s\n\n", transcript.URL)

	// Parse SRT into frames
	frames := ParseSRT(transcript.TranscriptText)
	fmt.Printf("Parsed %d frames from SRT\n\n", len(frames))

	// Show first 5 frames
	fmt.Println("First 5 frames:")
	for i := 0; i < 5 && i < len(frames); i++ {
		fmt.Printf("Frame %d:\n", i)
		fmt.Printf("  Start: %s\n", frames[i].StartTime)
		fmt.Printf("  Text: %s\n\n", frames[i].Text)
	}

	// Extract sentences from frames
	sentences := ExtractSentencesFromFrames(frames)
	fmt.Printf("Extracted %d sentences\n\n", len(sentences))

	// Show first 5 sentences
	fmt.Println("First 5 sentences:")
	for i := 0; i < 5 && i < len(sentences); i++ {
		fmt.Printf("Sentence %d:\n", i)
		fmt.Printf("  Start: %s\n", sentences[i].StartTime)
		if len(sentences[i].Text) > 100 {
			fmt.Printf("  Text: %s...\n\n", sentences[i].Text[:100])
		} else {
			fmt.Printf("  Text: %s\n\n", sentences[i].Text)
		}
	}

	// Embed sentences
	fmt.Println("Embedding sentences...")
	sentenceTexts := make([]string, len(sentences))
	for i, s := range sentences {
		sentenceTexts[i] = s.Text
	}

	embeddings, err := embeddingModel.EmbedSentences(sentenceTexts)
	if err != nil {
		log.Fatalf("Failed to embed sentences: %v", err)
	}

	// Assign embeddings back to sentences
	for i, embedding := range embeddings {
		sentences[i].Embedding = embedding
	}

	fmt.Printf("Successfully embedded %d sentences\n\n", len(sentences))

	// Show first 3 sentence embeddings
	fmt.Println("First 3 sentence embeddings (first 10 values):")
	for i := 0; i < 3 && i < len(sentences); i++ {
		fmt.Printf("Sentence %d embedding (length %d):\n", i, len(sentences[i].Embedding))
		if len(sentences[i].Embedding) >= 10 {
			fmt.Printf("  [%.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f...]\n\n",
				sentences[i].Embedding[0], sentences[i].Embedding[1], sentences[i].Embedding[2],
				sentences[i].Embedding[3], sentences[i].Embedding[4], sentences[i].Embedding[5],
				sentences[i].Embedding[6], sentences[i].Embedding[7], sentences[i].Embedding[8],
				sentences[i].Embedding[9])
		}
	}

	// Perform semantic chunking with default config
	fmt.Println("Performing semantic chunking...")
	chunkingCfg := DefaultChunkingConfig()
	chunks := chunkingCfg.ExtractChunksFromSentences(sentences, float32(config.SimilarityThreshold))
	fmt.Printf("Created %d chunks from %d sentences\n\n", len(chunks), len(sentences))

	// Finalize chunk embeddings with accurate model embeddings
	fmt.Println("Finalizing chunk embeddings...")
	err = FinalizeChunkEmbeddings(chunks, embeddingModel)
	if err != nil {
		log.Fatalf("Failed to finalize chunk embeddings: %v", err)
	}
	fmt.Println("Successfully finalized chunk embeddings\n")

	// Show chunk statistics
	fmt.Println("Chunk statistics:")
	for i, chunk := range chunks {
		fmt.Printf("Chunk %d:\n", i)
		fmt.Printf("  Sentences: %d\n", chunk.NumSentences)
		fmt.Printf("  Tokens: %d\n", chunk.TokenCount)
		fmt.Printf("  Start time: %s\n", chunk.StartTime)
		if len(chunk.Text) > 100 {
			fmt.Printf("  Text: %s...\n\n", chunk.Text[:100])
		} else {
			fmt.Printf("  Text: %s\n\n", chunk.Text)
		}
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
