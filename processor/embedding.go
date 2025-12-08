package main

import (
	"fmt"
	"path/filepath"

	tokenizer "github.com/sugarme/tokenizer"
	"github.com/sugarme/tokenizer/pretrained"
	ort "github.com/yalue/onnxruntime_go"
)

// EmbeddingModel manages ONNX Runtime embedding model
type EmbeddingModel struct {
	Tokenizer *tokenizer.Tokenizer
	session   *ort.DynamicAdvancedSession
	config    EmbeddingConfig
}

// InitEmbeddingModel loads the ONNX model and tokenizer
func InitEmbeddingModel(config EmbeddingConfig) (*EmbeddingModel, error) {
	// Load tokenizer
	tokenizerPath := filepath.Join(".", "tokenizer.json")
	tok, err := pretrained.FromFile(tokenizerPath)
	if err != nil {
		return nil, fmt.Errorf("failed to load tokenizer: %w", err)
	}

	// inside docker container
	ort.SetSharedLibraryPath("/usr/local/lib/libonnxruntime.so.1.23.2")

	err = ort.InitializeEnvironment()
	if err != nil {
		return nil, fmt.Errorf("failed to initialize ONNX environment: %w", err)
	}

	opts, err := ort.NewSessionOptions()
	if err != nil {
		return nil, fmt.Errorf("failed to create session options: %w", err)
	}
	defer opts.Destroy()

	err = opts.SetGraphOptimizationLevel(ort.GraphOptimizationLevelEnableAll)
	if err != nil {
		return nil, fmt.Errorf("failed to set graph optimization: %w", err)
	}

	// Try to enable CUDA
	cudaOpts, err := ort.NewCUDAProviderOptions()
	if err == nil {
		fmt.Println("CUDA provider options created successfully")
		// Configure CUDA options and append to opts
		err = cudaOpts.Update(map[string]string{
			"device_id": "0", // Use GPU 0
		})
		if err == nil {
			fmt.Println("CUDA options updated successfully")
			err = opts.AppendExecutionProviderCUDA(cudaOpts)
			if err == nil {
				fmt.Println("CUDA execution provider enabled (using GPU)")
			} else {
				fmt.Printf("Failed to append CUDA provider: %v\n", err)
			}
		} else {
			fmt.Printf("Failed to update CUDA options: %v\n", err)
		}
		cudaOpts.Destroy()
	} else {
		fmt.Printf("CUDA not available, using CPU: %v\n", err)
	}

	// Otherwise, use CPU
	err = opts.SetIntraOpNumThreads(0) // 0 = use all available
	if err != nil {
		fmt.Printf("Warning: Failed to set thread count: %v\n", err)
	}

	// Load ONNX model
	modelPath := filepath.Join(".", "model.onnx")

	session, err := ort.NewDynamicAdvancedSession(
		modelPath,
		[]string{"input_ids", "attention_mask", "token_type_ids"}, // Input names
		[]string{"last_hidden_state"},                             // Output names
		opts,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create session: %w", err)
	}

	return &EmbeddingModel{
		Tokenizer: tok,
		session:   session,
		config:    config,
	}, nil
}

// EmbedSentences embeds a slice of Sentence structs
func (em *EmbeddingModel) EmbedSentences(sentences []*Sentence) error {
	if len(sentences) == 0 {
		return nil
	}

	texts := make([]string, len(sentences))
	tokenCounts := make([]int, len(sentences))
	for i, s := range sentences {
		texts[i] = s.Text
		tokenCounts[i] = s.TokenCount
	}

	embeddings, err := em.embedBatches(texts, tokenCounts)
	if err != nil {
		return err
	}

	for i, emb := range embeddings {
		sentences[i].Embedding = emb
	}
	return nil
}

// EmbedChunks embeds a slice of Chunk structs (updates Embedding field in place)
func (em *EmbeddingModel) EmbedChunks(chunks []*Chunk) error {
	if len(chunks) == 0 {
		return nil
	}

	texts := make([]string, len(chunks))
	tokenCounts := make([]int, len(chunks))
	for i, c := range chunks {
		texts[i] = c.Text
		tokenCounts[i] = c.TokenCount
	}

	embeddings, err := em.embedBatches(texts, tokenCounts)
	if err != nil {
		return err
	}

	for i, emb := range embeddings {
		chunks[i].Embedding = emb
	}
	return nil
}

// embedBatches processes texts in multiple batches
func (em *EmbeddingModel) embedBatches(texts []string, tokenLengths []int) ([][]float32, error) {
	if len(texts) == 0 {
		return [][]float32{}, nil
	}
	if len(tokenLengths) != len(texts) {
		return nil, fmt.Errorf("tokenCount length does not match text length")
	}

	allEmbeddings := make([][]float32, 0, len(texts))

	i := 0
	for i < len(texts) {
		batchTexts := []string{}
		maxSeqLen := 0

		for i < len(texts) {
			newMaxSeqLen := maxSeqLen
			if tokenLengths[i] > newMaxSeqLen {
				newMaxSeqLen = tokenLengths[i]
			}

			// Calculate total tokens with this text added
			totalTokens := (len(batchTexts) + 1) * newMaxSeqLen

			// Check if adding this text would exceed budget
			if len(batchTexts) > 0 && totalTokens > em.config.MaxBatchTokens {
				break
			}

			batchTexts = append(batchTexts, texts[i])
			maxSeqLen = newMaxSeqLen
			i++
		}

		// Process batch
		embeddings, err := em.embedBatch(batchTexts)
		if err != nil {
			return nil, fmt.Errorf("batch failed: %w", err)
		}

		allEmbeddings = append(allEmbeddings, embeddings...)
	}

	return allEmbeddings, nil
}

// embedBatch processes a single batch of texts
func (em *EmbeddingModel) embedBatch(texts []string) ([][]float32, error) {
	// Tokenize all texts
	inputs := make([]tokenizer.EncodeInput, len(texts))
	for i, t := range texts {
		inputs[i] = tokenizer.NewSingleEncodeInput(tokenizer.NewInputSequence(t))
	}

	encodings, err := em.Tokenizer.EncodeBatch(inputs, true)
	if err != nil {
		return nil, fmt.Errorf("tokenization failed: %w", err)
	}

	// Find max sequence length
	maxLen := 0
	for _, enc := range encodings {
		if l := len(enc.GetIds()); l > maxLen {
			maxLen = l
		}
	}

	// Prepare input tensors with padding
	batchSize := len(encodings)

	// Flatten input_ids
	inputIds := make([]int64, batchSize*maxLen)
	attentionMask := make([]int64, batchSize*maxLen)
	tokenTypeIds := make([]int64, batchSize*maxLen)

	for i, enc := range encodings {
		tid := enc.GetIds()
		am := enc.GetAttentionMask()

		offset := i * maxLen
		for j := 0; j < maxLen; j++ {
			if j < len(tid) {
				inputIds[offset+j] = int64(tid[j])
				attentionMask[offset+j] = int64(am[j])
				// tokenTypeIds stays 0 (already initialized)
			}
		}
	}

	// Create input tensors
	inputIdsTensor, err := ort.NewTensor(ort.NewShape(int64(batchSize), int64(maxLen)), inputIds)
	if err != nil {
		return nil, fmt.Errorf("failed to create input_ids tensor: %w", err)
	}
	defer inputIdsTensor.Destroy()

	attentionMaskTensor, err := ort.NewTensor(ort.NewShape(int64(batchSize), int64(maxLen)), attentionMask)
	if err != nil {
		return nil, fmt.Errorf("failed to create attention_mask tensor: %w", err)
	}
	defer attentionMaskTensor.Destroy()

	tokenTypeIdsTensor, err := ort.NewTensor(ort.NewShape(int64(batchSize), int64(maxLen)), tokenTypeIds)
	if err != nil {
		return nil, fmt.Errorf("failed to create token_type_ids tensor: %w", err)
	}
	defer tokenTypeIdsTensor.Destroy()

	// Run inference

	// Pre-allocate output tensor with known shape
	outputs := make([]ort.Value, 1)

	err = em.session.Run(
		[]ort.Value{inputIdsTensor, attentionMaskTensor, tokenTypeIdsTensor},
		outputs,
	)
	if err != nil {
		return nil, fmt.Errorf("inference failed: %w", err)
	}
	defer outputs[0].Destroy()

	// Type assert to concrete tensor type to access GetData()
	outputTensor, ok := outputs[0].(*ort.Tensor[float32])
	if !ok {
		return nil, fmt.Errorf("output tensor is not float32 type")
	}

	outputShape := outputTensor.GetShape()

	// Output: [batch_size, sequence_length, hidden_dim]
	batchSizeOut := outputShape[0]
	seqLen := outputShape[1]
	hiddenDim := outputShape[2]

	// Get raw float32 data
	outputData := outputTensor.GetData()

	// Extract [CLS] token embedding (first token of each sequence)
	// IMPORTANT: Copy the data before the output tensor is destroyed
	embeddings := make([][]float32, batchSizeOut)
	for i := int64(0); i < batchSizeOut; i++ {
		clsStart := i * seqLen * hiddenDim
		clsEnd := clsStart + hiddenDim
		// Make a copy so we don't reference the tensor's memory after it's destroyed
		embeddings[i] = make([]float32, hiddenDim)
		copy(embeddings[i], outputData[clsStart:clsEnd])
	}
	return embeddings, nil
}

// Close releases resources
func (em *EmbeddingModel) Close() error {
	if em.session != nil {
		em.session.Destroy()
	}
	ort.DestroyEnvironment()
	return nil
}
