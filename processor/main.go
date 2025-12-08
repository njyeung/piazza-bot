package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	gocql "github.com/apache/cassandra-gocql-driver/v2"
	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

// TranscriptEvent represents the Kafka message structure
type TranscriptEvent struct {
	ClassName     string `json:"class_name"`
	Professor     string `json:"professor"`
	Semester      string `json:"semester"`
	URL           string `json:"url"`
	LectureNumber int    `json:"lecture_number"`
	LectureTitle  string `json:"lecture_title"`
}

func main() {
	// Load configurations
	kafkaConfig := LoadKafkaConfig()
	cassandraConfig := LoadCassandraConfig()
	embeddingConfig := DefaultEmbeddingConfig()

	// Create Kafka consumer
	fmt.Printf("Connecting to Kafka at %s\n", kafkaConfig.BootstrapServers)
	consumer, err := kafka.NewConsumer(&kafka.ConfigMap{
		"bootstrap.servers": kafkaConfig.BootstrapServers,
		"group.id":          kafkaConfig.GroupID,
		"auto.offset.reset": "earliest",
	})
	if err != nil {
		log.Fatalf("Failed to create Kafka consumer: %v", err)
	}
	defer consumer.Close()

	// Subscribe to topic
	fmt.Printf("Subscribing to topic: %s\n", kafkaConfig.Topic)
	err = consumer.SubscribeTopics([]string{kafkaConfig.Topic}, nil)
	if err != nil {
		log.Fatalf("Failed to subscribe to topic: %v", err)
	}

	// Connect to Cassandra
	fmt.Printf("Connecting to Cassandra at %v\n", cassandraConfig.CassandraHosts)
	session, err := ConnectCassandra(cassandraConfig)
	if err != nil {
		log.Fatalf("Failed to connect to Cassandra: %v", err)
	}
	defer session.Close()

	// Load embedding model
	fmt.Println("Loading embedding model")
	embeddingModel, err := InitEmbeddingModel(embeddingConfig)
	if err != nil {
		log.Fatalf("Failed to load embedding model: %v", err)
	}
	defer embeddingModel.Close()

	// signal handling
	sigchan := make(chan os.Signal, 1)
	signal.Notify(sigchan, syscall.SIGINT, syscall.SIGTERM)

	// Poll for messages
	run := true
	for run {
		select {
		case sig := <-sigchan:
			fmt.Printf("\nCaught signal %v: terminating\n", sig)
			run = false
		default:
			ev := consumer.Poll(500)
			if ev == nil {
				continue
			}

			switch e := ev.(type) {
			case *kafka.Message:
				fmt.Printf("\n=== Received transcript event ===\n")

				// Parse the event
				var event TranscriptEvent
				if err := json.Unmarshal(e.Value, &event); err != nil {
					fmt.Printf("Error parsing message: %v\n", err)
					continue
				}

				fmt.Printf("Processing: %s - %s - Lecture %d\n",
					event.ClassName, event.LectureTitle, event.LectureNumber)

				if err := process(session, embeddingModel, &event); err != nil {
					fmt.Printf("Error processing transcript: %v\n", err)
					continue
				}

				fmt.Println("Successfully processed transcript")

			case kafka.Error:
				fmt.Fprintf(os.Stderr, "Error: %v\n", e)
				if e.Code() == kafka.ErrAllBrokersDown {
					run = false
				}
			}
		}
	}
}

// fetches a transcript from Cassandra and processes it
func process(session *gocql.Session, embeddingModel *EmbeddingModel, event *TranscriptEvent) error {
	// Fetch transcript from Cassandra
	transcript, err := FetchTranscriptByKey(session, event.ClassName, event.Professor, event.Semester, event.URL)
	if err != nil {
		return fmt.Errorf("failed to fetch transcript: %w", err)
	}
	fmt.Printf("\tRetrieved transcript (%d characters)\n", len(transcript.TranscriptText))

	// Parse SRT into frames
	frames := ParseSRT(transcript.TranscriptText)
	fmt.Printf("\tParsed %d frames from SRT\n", len(frames))

	// Extract sentences from frames
	sentences := embeddingModel.ExtractSentencesFromFrames(frames)
	fmt.Printf("\tExtracted %d sentences\n", len(sentences))

	// Embed sentences
	if err := embeddingModel.EmbedSentences(sentences); err != nil {
		return fmt.Errorf("failed to embed sentences: %w", err)
	}
	fmt.Printf("\tEmbedded %d sentences\n", len(sentences))

	// Perform semantic chunking
	chunkingCfg := DefaultChunkingConfig()
	chunks, err := chunkingCfg.ExtractChunksFromSentences(sentences)
	if err != nil {
		return fmt.Errorf("failed to extract chunks: %w", err)
	}
	fmt.Printf("\tCreated %d chunks\n", len(chunks))

	// Embed chunks
	if err := embeddingModel.EmbedChunks(chunks); err != nil {
		return fmt.Errorf("failed to embed chunks: %w", err)
	}
	fmt.Printf("\tEmbedded %d chunks\n", len(chunks))

	// Store chunks in Cassandra embeddings table
	fmt.Printf("\tInserting %d chunks into Cassandra...\n", len(chunks))
	for i, chunk := range chunks {
		row := &EmbeddingsRow{
			ClassName:        event.ClassName,  // partition key
			Professor:        event.Professor,  // partition key
			Semester:         event.Semester,   // partition key
			URL:              event.URL,        // cluster key
			ChunkIndex:       chunk.ChunkIndex, // cluster key
			ChunkText:        chunk.Text,
			Embedding:        chunk.Embedding, // embedding search
			TokenCount:       chunk.TokenCount,
			LectureTitle:     event.LectureTitle,
			LectureTimestamp: chunk.StartTime,
		}

		if err := InsertEmbedding(session, row); err != nil {
			return fmt.Errorf("failed to insert chunk %d: %w", i, err)
		}
	}
	fmt.Printf("\tInserted %d chunks to database\n", len(chunks))

	return nil
}
