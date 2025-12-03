package main

// Config holds configuration for the processor
type Config struct {
	CassandraHosts      []string
	CassandraKeyspace   string
	GTPLargeModel       string
	SimilarityThreshold float64
}

// LoadConfig returns hardcoded config for testing
func LoadConfig() *Config {
	return &Config{
		CassandraHosts:      []string{"localhost"},
		CassandraKeyspace:   "transcript_db",
		SimilarityThreshold: 0.75,
	}
}
