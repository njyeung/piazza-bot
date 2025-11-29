package main

import (
	"os"
	"strings"
	"time"
)

// Config holds configuration from environment variables
type Config struct {
	CassandraHosts    []string
	CassandraKeyspace string
	PollInterval      time.Duration
	ParsersDir        string
	RedisHost         string
	RedisPort         string
	RedisQueue        string
	RedisSeenSet      string
}

// LoadConfig loads configuration from environment variables
func LoadConfig() *Config {
	hostsEnv := os.Getenv("CASSANDRA_HOSTS")

	// Split comma-separated hosts
	hosts := strings.Split(hostsEnv, ",")

	keyspace := os.Getenv("CASSANDRA_KEYSPACE")

	pollInterval := 60 * time.Second

	parsersDir := "./parsers"

	redisHost := os.Getenv("REDIS_HOST")

	redisPort := os.Getenv("REDIS_PORT")

	redisQueue := os.Getenv("REDIS_QUEUE")

	redisSeenSet := os.Getenv("REDIS_SEEN_SET")

	return &Config{
		CassandraHosts:    hosts,
		CassandraKeyspace: keyspace,
		PollInterval:      pollInterval,
		ParsersDir:        parsersDir,
		RedisHost:         redisHost,
		RedisPort:         redisPort,
		RedisQueue:        redisQueue,
		RedisSeenSet:      redisSeenSet,
	}
}
