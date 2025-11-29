package main

import (
	"log"
	"os"
	"strings"
	"time"

	"github.com/gocql/gocql"
)

func main() {
	log.Println("=== Watcher Starting ===")

	// Load configuration
	config := LoadConfig()
	log.Printf("Configuration:")
	log.Printf("  Cassandra hosts: %v", config.CassandraHosts)
	log.Printf("  Keyspace: %s", config.CassandraKeyspace)
	log.Printf("  Poll interval: %v", config.PollInterval)
	log.Printf("  Parsers directory: %s", config.ParsersDir)
	log.Printf("  Redis: %s:%s", config.RedisHost, config.RedisPort)
	log.Printf("  Queue: %s, Seen set: %s", config.RedisQueue, config.RedisSeenSet)
	log.Println()

	// Connect to Cassandra
	log.Println("Connecting to Cassandra...")
	session, err := ConnectCassandra(config)
	if err != nil {
		log.Fatalf("Failed to connect to Cassandra: %v", err)
	}
	defer session.Close()
	log.Println("Connected to Cassandra")

	// Connect to Redis
	log.Println("Connecting to Redis...")
	redisClient, err := ConnectRedis(config)
	if err != nil {
		log.Fatalf("Failed to connect to Redis: %v", err)
	}
	defer redisClient.Close()
	log.Println("Connected to Redis")
	log.Println()

	// Main polling loop uses a greedy strategy
	for {
		cycleStart := time.Now()

		// Run both functions
		updateParsers(session, config.ParsersDir)
		runParsers(config.ParsersDir, redisClient)

		// Calculate elapsed time
		elapsed := time.Since(cycleStart)

		// Sleep for remaining time if we finished early
		// Otherwise start immediately again.
		if elapsed < config.PollInterval {
			remaining := config.PollInterval - elapsed
			log.Printf("Sleeping for %v until next cycle\n", remaining)
			time.Sleep(remaining)
		} else {
			log.Printf("Cycle took longer than poll interval, running immediately\n")
		}
	}
}

func updateParsers(session *gocql.Session, parsersDir string) {
	log.Printf("[%s] Polling Cassandra for parsers...", time.Now().Format("2006-01-02 15:04:05"))

	parsers, err := FetchParsers(session)
	if err != nil {
		log.Printf("Error fetching parsers: %v", err)
		return
	}

	log.Printf("Found %d parser(s) in Cassandra", len(parsers))

	// Clean up parsers that were deleted from Cassandra
	if err := CleanupDeletedParsers(parsers, parsersDir); err != nil {
		log.Printf("Error cleaning up deleted parsers: %v", err)
	}

	// Write current parsers to disk
	if len(parsers) > 0 {
		if err := WriteParsersToDisk(parsers, parsersDir); err != nil {
			log.Printf("Error writing parsers to disk: %v", err)
			return
		}

		log.Println("Parsers written to disk:")
		for _, p := range parsers {
			log.Printf("  - %s", p.ParserName)
		}
	}

	log.Println()
}

func runParsers(parsersDir string, redisClient *RedisClient) {
	log.Printf("[%s] Running parsers...", time.Now().Format("2006-01-02 15:04:05"))

	// Get list of parser files
	entries, err := os.ReadDir(parsersDir)
	if err != nil {
		log.Printf("Error reading parsers directory: %v", err)
		return
	}

	// Filter for .py files
	var parserNames []string
	for _, entry := range entries {
		if !entry.IsDir() && strings.HasSuffix(entry.Name(), ".py") {
			parserName := strings.TrimSuffix(entry.Name(), ".py")
			parserNames = append(parserNames, parserName)
		}
	}

	if len(parserNames) == 0 {
		log.Println("No parsers to run")
		log.Println()
		return
	}

	log.Printf("Found %d parser(s) to execute\n", len(parserNames))

	// Track statistics
	totalLectures := 0
	newLectures := 0

	for _, parserName := range parserNames {
		lectures, err := ExecuteParser(parserName, parsersDir)
		if err != nil {
			log.Printf("  Error executing %s: %v", parserName, err)
			continue
		}

		log.Printf("  %s returned %d lecture(s)", parserName, len(lectures))
		totalLectures += len(lectures)

		// Add each lecture to Redis queue
		for _, lecture := range lectures {
			added, err := redisClient.AddLecture(lecture)
			if err != nil {
				log.Printf("    Error adding lecture to Redis: %v", err)
				continue
			}
			if added {
				newLectures++
				log.Printf("    Queued: %s", lecture.URL)
			} else {
				log.Printf("    Skipped (already seen): %s", lecture.URL)
			}
		}
	}

	log.Printf("\nSummary: %d total lectures, %d new, %d already seen\n", totalLectures, newLectures, totalLectures-newLectures)
}
