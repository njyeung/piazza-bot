package main

import (
	"errors"
	"fmt"
	"math"
	"strings"
)

// Calculates hinge loss based on tokens window.
// Returns (penalty, legal) where legal=false means the segment is illegal (exceeds MaxSize)
func (cfg ChunkingConfig) ComputePenalty(i, j int, prefixTokens []int) (penalty float32, legal bool) {
	tokenCount := prefixTokens[j] - prefixTokens[i]

	// Hard constraint: illegal if we exceed MaxSize
	if tokenCount > cfg.MaxSize {
		return 0, false
	}

	if tokenCount <= cfg.OptimalSize {
		return 0, true
	}

	normalized := float32(tokenCount-cfg.OptimalSize) / float32(cfg.MaxSize-cfg.OptimalSize)
	return cfg.LambdaSize * normalized, true
}

// SegmentReward computes the sum of similarities between adjacent sentences in a segment [i..j-1]
func SegmentReward(i, j int, prefixSim []float32) float32 {
	if j-i <= 1 {
		return 0 // Single sentence has no internal edges
	}
	return prefixSim[j-1] - prefixSim[i]
}

// Partition sentences into chunks. Maximizes semantic coherence while penalizing oversized chunks
func (cfg ChunkingConfig) ExtractChunksFromSentences(sentences []*Sentence) ([]*Chunk, error) {
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

	// Edge cases
	if len(sentences) == 0 {
		return []*Chunk{}, nil
	}
	if len(sentences) == 1 {
		chunk := &Chunk{
			StartTime:          sentences[0].StartTime,
			NumSentences:       1,
			SentenceEmbeddings: [][]float32{sentences[0].Embedding},
			ChunkIndex:         0,
			TokenCount:         sentences[0].TokenCount,
			Text:               sentences[0].Text,
			Embedding:          sentences[0].Embedding,
		}
		return []*Chunk{chunk}, nil
	}

	n := len(sentences)

	// Sanity check: every sentence must fit within MaxSize
	for idx, s := range sentences {
		if s.TokenCount > cfg.MaxSize {
			return nil, fmt.Errorf("sentence %d has TokenCount=%d > MaxSize=%d; cannot chunk (issue with ExtractSentencesFromFrames)", idx, s.TokenCount, cfg.MaxSize)
		}
	}

	// precompute adjacent cosine similarities
	sim := make([]float32, n-1)
	for i := 0; i < n-1; i++ {
		if sentences[i].Embedding == nil {
			return nil, fmt.Errorf("sentence %d Embedding is nil. Please use EmbedSentences first.", i)
		}
		if sentences[i+1].Embedding == nil {
			return nil, fmt.Errorf("sentence %d Embedding is nil. Please use EmbedSentences first.", i+1)
		}
		sim[i], _ = CosineSimilarity(sentences[i].Embedding, sentences[i+1].Embedding)
	}

	// Min-max normalizes similarities to [0, 1] range to keep rewards positive
	// This ensures that merging similar sentences is always rewarded
	// while dissimilar sentences get less reward but never negative
	minSim := sim[0]
	maxSim := sim[0]
	for _, v := range sim {
		if v < minSim {
			minSim = v
		}
		if v > maxSim {
			maxSim = v
		}
	}
	// Normalize to [0, 1]
	simRange := maxSim - minSim
	if simRange == 0 {
		// All similarities are the same, set to 0.5
		for i := range sim {
			sim[i] = 0.5
		}
	} else {
		for i, v := range sim {
			sim[i] = (v - minSim) / simRange
		}
	}

	// prefixSim and prefixTokens are prefix-sum arrays over adjacent sentence
	// similarities and tokens.
	//
	// For example, The constructed prefixSim array looks like:
	// prefixSim[0] = sim[0]
	// prefixSim[1] = sim[0] + sim[1]
	// prefixSim[2] = sim[0] + sim[1] + sim[2]
	// ...
	//
	// This allows constant-time computation of the total similarity
	// and total tokens inside any candidate chunk [i...j-1]:
	//
	//   prefixSim[j-1] - prefixSim[i]
	//
	// While it is more accurate to calculate the pairwise cosine similarity
	// of sentences [i...j-1], this approximation makes similarity-based
	// segment scoring O(1) per DP transition.
	prefixSim := make([]float32, n+1)
	prefixSim[0] = 0
	for i := 0; i < n-1; i++ {
		prefixSim[i+1] = prefixSim[i] + sim[i]
	}
	if n > 0 {
		prefixSim[n] = prefixSim[n-1]
	}
	// Build prefix sums for token counts
	prefixTokens := make([]int, n+1)
	prefixTokens[0] = 0
	for i := 0; i < n; i++ {
		prefixTokens[i+1] = prefixTokens[i] + sentences[i].TokenCount
	}

	dp := make([]float32, n+1)
	dp[0] = 0

	start := make([]int, n+1)
	start[0] = 0
	// all other start values to -1 (invalid)
	for i := 1; i <= n; i++ {
		start[i] = -1
	}

	for j := 1; j <= n; j++ {
		dp[j] = float32(math.Inf(-1))

		for i := 0; i < j; i++ {
			if math.IsInf(float64(dp[i]), -1) {
				continue // Skip unreachable parents
			}

			penalty, legal := cfg.ComputePenalty(i, j, prefixTokens)
			if !legal {
				continue // Segment too large, skip
			}

			reward := SegmentReward(i, j, prefixSim)

			// Score = previous best + reward for this segment - size penalty - per-chunk penalty
			score := dp[i] + reward - penalty - cfg.ChunkPenalty

			if score > dp[j] {
				dp[j] = score
				start[j] = i
			}
		}
	}

	// Check if DP failed to find a valid solution
	if math.IsInf(float64(dp[n]), -1) || start[n] == -1 {
		return nil, fmt.Errorf("DP failed: no valid segmentation found under MaxSize=%d; could be error in preprocessing", cfg.MaxSize)
	}

	// Reconstruct chunks from parent pointers
	var chunks []*Chunk
	var chunkIndex int
	pos := n

	for pos > 0 {
		prevPos := start[pos]
		chunkSentences := sentences[prevPos:pos]

		// Build chunk
		chunk := &Chunk{
			StartTime:          chunkSentences[0].StartTime,
			NumSentences:       len(chunkSentences),
			SentenceEmbeddings: make([][]float32, len(chunkSentences)),
			ChunkIndex:         chunkIndex,
			Embedding:          nil, // handled by EmbedChunks()
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

	return chunks, nil
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

	return dotProduct / (normA * normB), nil
}
