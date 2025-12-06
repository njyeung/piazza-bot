package main

// Config holds configuration for the processor
type CassandraConfig struct {
	CassandraHosts    []string
	CassandraKeyspace string
}

// ChunkingConfig holds all tunable parameters for the semantic chunking algorithm
type ChunkingConfig struct {
	OptimalSize  int     // optimal chunk size, no penalty below this (default: 470)
	MaxSize      int     // chunk size hard limit, infinite penalty at or above (default: 512)
	LambdaSize   float32 // Max penalty in "edge units" at MaxSize (default: 3.0)
	ChunkPenalty float32 // Initial penalty per chunk to discourage small chunks (default: 1.0)
}

// EmbeddingConfig holds embedding model configuration
type EmbeddingConfig struct {
	MaxBatchTokens int // Max total tokens per batch (controls GPU memory usage)
}

// cassandra config
func LoadCassandraConfig() *CassandraConfig {
	return &CassandraConfig{
		CassandraHosts:    []string{"host.docker.internal"},
		CassandraKeyspace: "transcript_db",
	}
}

// DefaultEmbeddingConfig returns sensible defaults for embedding
func DefaultEmbeddingConfig() EmbeddingConfig {
	return EmbeddingConfig{
		// 12000 tokens is about:
		// 240 short sentences (50 tokens each) in one batch
		// 24 medium chunks (500 tokens each) in one batch
		// 12 large chunks (1000 tokens each) in one batch
		MaxBatchTokens: 12000,
	}
}

// DefaultChunkingConfig returns sensible defaults
func DefaultChunkingConfig() ChunkingConfig {
	return ChunkingConfig{
		OptimalSize:  470,
		MaxSize:      512,
		LambdaSize:   3.0,
		ChunkPenalty: 1.0,
	}
}
