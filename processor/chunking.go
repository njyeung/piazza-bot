package main

import (
	"errors"
	"math"
)

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

// SemanticChunk groups sentences into chunks based on embedding similarity
// Sentences with cosine similarity >= threshold are grouped together
func SemanticChunk(sentences []Sentence, threshold float32) []Chunk {
	if len(sentences) == 0 {
		return []Chunk{}
	}

	var chunks []Chunk
	currentChunk := Chunk{
		StartTime:          sentences[0].StartTime,
		SentenceEmbeddings: [][]float32{sentences[0].Embedding},
		TokenCount:         sentences[0].TokenCount,
		NumSentences:       1,
		ChunkIndex:         0,
	}
	currentChunk.Text = sentences[0].Text

	for i := 1; i < len(sentences); i++ {
		// Calculate similarity between current sentence and previous sentence
		similarity, err := CosineSimilarity(sentences[i-1].Embedding, sentences[i].Embedding)
		if err != nil {
			similarity = 0
		}

		// If similarity is below threshold, start a new chunk
		if similarity < threshold {
			// Add averaged embedding to current chunk
			currentChunk.Embedding = averageEmbeddings(currentChunk.SentenceEmbeddings)

			chunks = append(chunks, currentChunk)

			// Start new chunk
			currentChunk = Chunk{
				StartTime:          sentences[i].StartTime,
				SentenceEmbeddings: [][]float32{sentences[i].Embedding},
				TokenCount:         sentences[i].TokenCount,
				NumSentences:       1,
				ChunkIndex:         len(chunks),
			}
			currentChunk.Text = sentences[i].Text
		} else {
			// Add sentence to current chunk
			currentChunk.Text += " " + sentences[i].Text
			currentChunk.SentenceEmbeddings = append(currentChunk.SentenceEmbeddings, sentences[i].Embedding)
			currentChunk.TokenCount += sentences[i].TokenCount
			currentChunk.NumSentences++
		}
	}

	// Add the last chunk
	if currentChunk.NumSentences > 0 {
		currentChunk.Embedding = averageEmbeddings(currentChunk.SentenceEmbeddings)
		chunks = append(chunks, currentChunk)
	}

	return chunks
}

// averageEmbeddings computes the mean of a list of embedding vectors
func averageEmbeddings(embeddings [][]float32) []float32 {
	if len(embeddings) == 0 {
		return []float32{}
	}

	if len(embeddings[0]) == 0 {
		return []float32{}
	}

	dimension := len(embeddings[0])
	result := make([]float32, dimension)

	for _, embedding := range embeddings {
		for i := range embedding {
			result[i] += embedding[i]
		}
	}

	count := float32(len(embeddings))
	for i := range result {
		result[i] /= count
	}

	return result
}
