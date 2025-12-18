package main

import (
	"os"
	"strings"
)

// Config holds configuration for the processor
type CassandraConfig struct {
	CassandraHosts    []string
	CassandraKeyspace string
}

// KafkaConfig holds Kafka consumer configuration
type KafkaConfig struct {
	BootstrapServers string
	Topic            string
	GroupID          string
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
	cassandraHostsStr := os.Getenv("CASSANDRA_HOSTS")
	var cassandraHosts []string
	if cassandraHostsStr == "" {
		cassandraHosts = []string{"db-1", "db-2", "db-3"}
	} else {
		cassandraHosts = strings.Split(cassandraHostsStr, ",")
	}

	cassandraKeyspace := os.Getenv("CASSANDRA_KEYSPACE")
	if cassandraKeyspace == "" {
		cassandraKeyspace = "transcript_db"
	}

	return &CassandraConfig{
		CassandraHosts:    cassandraHosts,
		CassandraKeyspace: cassandraKeyspace,
	}
}

// LoadKafkaConfig loads Kafka configuration from environment variables
func LoadKafkaConfig() *KafkaConfig {
	bootstrapServers := os.Getenv("KAFKA_BOOTSTRAP_SERVERS")
	if bootstrapServers == "" {
		bootstrapServers = "kafka:9092"
	}

	topic := os.Getenv("KAFKA_TOPIC")
	if topic == "" {
		topic = "transcript-events"
	}

	return &KafkaConfig{
		BootstrapServers: bootstrapServers,
		Topic:            topic,
		GroupID:          "processor-group",
	}
}

// DefaultEmbeddingConfig returns sensible defaults for embedding
func DefaultEmbeddingConfig() EmbeddingConfig {
	return EmbeddingConfig{
		MaxBatchTokens: 6000,
	}
}

// DefaultChunkingConfig returns sensible defaults
func DefaultChunkingConfig() ChunkingConfig {
	return ChunkingConfig{
		OptimalSize:  470,
		MaxSize:      512,
		LambdaSize:   2.0,
		ChunkPenalty: 1.0,
	}
}
