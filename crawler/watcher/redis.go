package main

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/redis/go-redis/v9"
)

// RedisClient wraps the Redis client with our configuration
type RedisClient struct {
	client  *redis.Client
	queue   string
	seenSet string
	ctx     context.Context
}

// ConnectRedis establishes a connection to Redis
func ConnectRedis(config *Config) (*RedisClient, error) {
	client := redis.NewClient(&redis.Options{
		Addr: fmt.Sprintf("%s:%s", config.RedisHost, config.RedisPort),
	})

	// Test connection
	ctx := context.Background()
	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	return &RedisClient{
		client:  client,
		queue:   config.RedisQueue,
		seenSet: config.RedisSeenSet,
		ctx:     ctx,
	}, nil
}

// IsSeen checks if a URL has been seen before
func (r *RedisClient) IsSeen(url string) (bool, error) {
	result, err := r.client.SIsMember(r.ctx, r.seenSet, url).Result()
	if err != nil {
		return false, fmt.Errorf("error checking seen set: %w", err)
	}
	return result, nil
}

// AddLecture adds a lecture to both the seen set (by URL) and the queue (as JSON)
// Returns true if the lecture was newly added (not seen before)
func (r *RedisClient) AddLecture(lecture LectureInfo) (bool, error) {
	// Check if URL already seen
	seen, err := r.IsSeen(lecture.URL)
	if err != nil {
		return false, err
	}

	if seen {
		return false, nil
	}

	// Add URL to seen set
	if err := r.client.SAdd(r.ctx, r.seenSet, lecture.URL).Err(); err != nil {
		return false, fmt.Errorf("error adding to seen set: %w", err)
	}

	// Marshal lecture to JSON
	jsonData, err := json.Marshal(lecture)
	if err != nil {
		return false, fmt.Errorf("failed to marshal lecture to JSON: %w", err)
	}

	// Add JSON to queue
	if err := r.client.RPush(r.ctx, r.queue, string(jsonData)).Err(); err != nil {
		return false, fmt.Errorf("error adding to queue: %w", err)
	}

	return true, nil
}

// GetQueueLength returns the current length of the queue
func (r *RedisClient) GetQueueLength() (int64, error) {
	length, err := r.client.LLen(r.ctx, r.queue).Result()
	if err != nil {
		return 0, fmt.Errorf("error getting queue length: %w", err)
	}
	return length, nil
}

// GetSeenCount returns the number of URLs in the seen set
func (r *RedisClient) GetSeenCount() (int64, error) {
	count, err := r.client.SCard(r.ctx, r.seenSet).Result()
	if err != nil {
		return 0, fmt.Errorf("error getting seen count: %w", err)
	}
	return count, nil
}

// Close closes the Redis connection
func (r *RedisClient) Close() error {
	return r.client.Close()
}
