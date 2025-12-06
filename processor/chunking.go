package main

import (
	"errors"
	"math"
	"strings"
)

// Calculates hinge loss based on tokens window.
// 0 at OptimalSize, linearly increasing to lambda at MaxSize, then infinity
func (cfg ChunkingConfig) ComputePenalty(i int, j int, prefixTokens []int) float32 {
	tokenCount := prefixTokens[j] - prefixTokens[i]

	if tokenCount <= cfg.OptimalSize {
		return 0
	}

	if tokenCount >= cfg.MaxSize {
		return float32(math.MaxFloat32)
	}

	normalized := float32(tokenCount-cfg.OptimalSize) / float32(cfg.MaxSize-cfg.OptimalSize)
	return cfg.LambdaSize * normalized
}

// Partition sentences into chunks. Maximizes semantic coherence while penalizing oversized chunks
func (cfg ChunkingConfig) ExtractChunksFromSentences(sentences []Sentence) []Chunk {
	//
	// DP Definition:
	// dp[j] = best score for optimally chunking sentences 0..j-1
	// dp[0] = 0 (no sentences means a score of 0)
	//
	// Recurrence relation:
	// dp[j] = max{i < j} (dp[i] + reward(sentences[i..j-1]) - penalty(tokenCount[i..j-1]))
	//
	// Reward: sum of cosine similarities between adjacent sentences in the segment
	// Penalty: smooth increase as token count approaches limit (hinge loss)
	//
	// Reconstruction:
	// start[j] = optimal starting index i for the last chunk ending at j
	// Backtrack: pos = start[pos] until pos=0
	//

	if len(sentences) == 0 {
		return []Chunk{}
	}

	n := len(sentences)

	// precompute adjacent cosine similarities
	sim := make([]float32, n-1)
	for i := 0; i < n-1; i++ {
		sim[i], _ = CosineSimilarity(sentences[i].Embedding, sentences[i+1].Embedding)
	}

	// Z-score normalize similarities for reward scaling reward and penalty

	// mean
	var sum float64
	for _, v := range sim {
		sum += float64(v)
	}
	mean := sum / float64(len(sim))

	// std dev
	var sqSum float64
	for _, v := range sim {
		diff := float64(v) - mean
		sqSum += diff * diff
	}
	std := math.Sqrt(sqSum / float64(len(sim)))
	if std == 0 {
		std = 1 // avoid divide by 0 later
	}

	// Normalize to z-scores
	for i, v := range sim {
		sim[i] = float32((float64(v) - mean) / std)
	}

	prefixSim := make([]float32, n)
	prefixSim[0] = 0
	for i := 0; i < n-1; i++ {
		prefixSim[i+1] = prefixSim[i] + sim[i]
	}
	prefixTokens := make([]int, n+1)
	prefixTokens[0] = 0
	for i := 0; i < n; i++ {
		prefixTokens[i+1] = prefixTokens[i] + sentences[i].TokenCount
	}

	dp := make([]float32, n+1)
	dp[0] = 0

	start := make([]int, n+1)
	start[0] = 0

	for j := 1; j <= n; j++ {
		dp[j] = float32(math.Inf(-1))

		for i := 0; i < j; i++ {
			reward := SegmentReward(i, j, prefixSim)
			penalty := cfg.ComputePenalty(i, j, prefixTokens)

			// Score = previous best + reward for this segment - size penalty - per-chunk penalty
			score := dp[i] + reward - penalty - cfg.ChunkPenalty

			if score > dp[j] {
				dp[j] = score
				start[j] = i
			}
		}
	}

	// Reconstruct chunks from parent pointers
	var chunks []Chunk
	var chunkIndex int
	pos := n

	for pos > 0 {
		prevPos := start[pos]
		chunkSentences := sentences[prevPos:pos]

		// Build chunk
		chunk := Chunk{
			StartTime:          chunkSentences[0].StartTime,
			NumSentences:       len(chunkSentences),
			SentenceEmbeddings: make([][]float32, len(chunkSentences)),
			ChunkIndex:         chunkIndex,
		}

		tokenCount := 0
		textParts := make([]string, len(chunkSentences))

		for i, s := range chunkSentences {
			chunk.SentenceEmbeddings[i] = s.Embedding
			tokenCount += s.TokenCount
			textParts[i] = s.Text
		}

		chunk.TokenCount = tokenCount
		chunk.Text = strings.Join(textParts, " ")

		// Compute final embedding as average of sentence embeddings
		if len(chunkSentences) > 0 && len(chunkSentences[0].Embedding) > 0 {
			chunk.Embedding = make([]float32, len(chunkSentences[0].Embedding))
			for i := range chunk.Embedding {
				sum := float32(0)
				for _, sent := range chunkSentences {
					sum += sent.Embedding[i]
				}
				chunk.Embedding[i] = sum / float32(len(chunkSentences))
			}
		}

		chunks = append(chunks, chunk)
		pos = prevPos
		chunkIndex++
	}

	// Reverse chunks since we built them backwards
	for i := 0; i < len(chunks)/2; i++ {
		j := len(chunks) - 1 - i
		chunks[i], chunks[j] = chunks[j], chunks[i]
	}

	// Re-index chunks
	for i := range chunks {
		chunks[i].ChunkIndex = i
	}

	return chunks
}

// SegmentReward computes the sum of similarities between adjacent sentences in a segment [i..j-1]
func SegmentReward(i, j int, sim []float32) float32 {
	if j-i <= 1 {
		return 0 // Single sentence has no internal edges
	}
	// Sum of similarities from prefixSim[i] to prefixSim[j-1]
	return sim[j-1] - sim[i]
}

// a dot b / norm(a) norm(b)
func CosineSimilarity(a []float32, b []float32) (float32, error) {
	if len(a) != len(b) || len(a) == 0 {
		return 0, errors.New("different length vectors")
	}

	var (
		dotProduct float32
		normA      float32
		normB      float32
	)

	for i := range a {
		dotProduct += a[i] * b[i]
		normA += a[i] * a[i]
		normB += b[i] * b[i]
	}

	if normA == 0 || normB == 0 {
		return 0, errors.New("divide by zero")
	}

	normA = float32(math.Sqrt(float64(normA)))
	normB = float32(math.Sqrt(float64(normB)))

	return dotProduct / normA * normB, nil
}
