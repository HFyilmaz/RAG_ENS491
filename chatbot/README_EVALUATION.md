# RAG Evaluation System

This module provides tools to evaluate the performance of the RAG (Retrieval-Augmented Generation) system using synthetic question-answer pairs.

## Evaluation Pipeline

The evaluation process consists of three main steps:

1. **Generate QA Pairs**: Create synthetic question-answer pairs from the documents in your knowledge base.
2. **Filter QA Pairs**: Filter out low-quality QA pairs using an LLM-based critique agent.
3. **Evaluate RAG System**: Test the RAG system using the filtered QA pairs and generate performance metrics.

## QA Pair Structure

Each generated QA pair includes the following fields:

- `id`: Unique identifier for the QA pair
- `question`: The generated question
- `answer`: The reference answer
- `source`: Path to the source document
- `page`: Page number in the source document (if applicable)
- `chunk_content`: The text content of the document chunk

After filtering, QA pairs also include:
- `quality_scores`: Scores for various quality criteria
- `quality_evaluation`: Detailed evaluation of the QA pair quality

## Requirements

Ensure you have the required Python packages installed:

```bash
pip install matplotlib numpy pandas
```

## Usage

### Command-line Interface

The evaluation system provides a command-line interface to run each step of the pipeline:

#### Generate QA Pairs

```bash
cd Model/chatbot
python rag/evaluate_rag.py --generate-qa --pairs-per-doc 5
```

- `--pairs-per-doc`: Number of QA pairs to generate per document (default: 5)
- `--document-paths`: Optional list of document paths to generate QA pairs for (if not specified, all documents are used)
- `--output`: Optional path to save the output JSON

Example for generating QA pairs for specific documents:

```bash
python rag/evaluate_rag.py --generate-qa --pairs-per-doc 5 --document-paths /path/to/doc1.pdf /path/to/doc2.pdf
```

#### Filter QA Pairs

```bash
python rag/evaluate_rag.py --filter-qa --quality-threshold 0.7
```

- `--quality-threshold`: Minimum quality score (0-1) for a QA pair to pass the filter (default: 0.7)
- `--output`: Optional path to save the output JSON

#### Evaluate RAG System

```bash
python rag/evaluate_rag.py --evaluate
```

- `--output`: Optional path to save the output JSON

#### Run Full Pipeline

```bash
python rag/evaluate_rag.py --run-all
```

- `--force-regenerate`: Force regenerate QA pairs even if they already exist
- `--force-refilter`: Force refilter QA pairs even if filtered pairs already exist
- `--pairs-per-doc`: Number of QA pairs to generate per document (default: 5)
- `--quality-threshold`: Minimum quality score (0-1) for filtering (default: 0.7)
- `--document-paths`: Optional list of document paths to generate QA pairs for
- `--output`: Optional path to save the output JSON

### API Endpoints

The evaluation system also provides REST API endpoints:

#### Generate QA Pairs

```
POST /api/rag/evaluation/generate-qa-pairs/
```

Parameters:
- `total_pairs`: Total number of QA pairs to generate (default: 10)
- `document_ids`: Optional list of document IDs to generate QA pairs from

Example request:
```json
{
  "total_pairs": 10,
  "document_ids": [1, 2, 3]
}
```

#### Evaluate Single QA Pair

```
POST /api/rag/evaluation/evaluate-qa-pair/
```

Parameters:
- `id`: Optional ID of the QA pair
- `question`: The question to evaluate
- `reference_answer`: The reference answer to compare against

Example request:
```json
{
  "id": 42,
  "question": "What is the main purpose of the RAG system?",
  "reference_answer": "The main purpose of the RAG system is to enhance LLM responses with relevant context from a knowledge base."
}
```

### Visualize Results

After running the evaluation, you can visualize the results using the provided visualization script:

```bash
python rag/visualize_results.py
```

Options:
- `--results`: Path to the evaluation results JSON file (default: uses the most recent evaluation)
- `--output-dir`: Directory to save visualization charts (default: 'visualization')
- `--overall`: Generate overall metrics chart
- `--qa-metrics`: Generate per-question metrics chart
- `--all`: Generate all visualization charts (default if no specific charts are requested)

## Evaluation Metrics

The evaluation system measures the following metrics:

1. **Relevance**: How relevant is the generated answer to the question?
2. **Faithfulness**: Does the answer contain hallucinations or make claims not supported by the retrieved context?
3. **Context Precision**: Were the retrieved contexts helpful and necessary for answering the question?
4. **Answer Correctness**: How correct is the generated answer compared to the reference answer?
5. **Overall Score**: The average of the above metrics.

## Output Files

The evaluation system generates the following output files:

- `rag/evaluation_data/qa_pairs.json`: Generated QA pairs
- `rag/evaluation_data/filtered_qa_pairs.json`: Filtered high-quality QA pairs
- `rag/evaluation_data/evaluation_results.json`: Detailed evaluation results

## Using Results for Model Comparison

To compare different RAG configurations:

1. Run the evaluation pipeline for each configuration
2. Save the results to different output files using the `--output` option
3. Visualize and compare the results

Example comparison workflow:

```bash
# Evaluate configuration 1
python rag/evaluate_rag.py --run-all --output results_config1.json

# Evaluate configuration 2 (e.g., with different LLM)
# First modify your configuration
python rag/evaluate_rag.py --run-all --output results_config2.json

# Visualize and compare
python rag/visualize_results.py --results results_config1.json --output-dir viz_config1
python rag/visualize_results.py --results results_config2.json --output-dir viz_config2
```

## Extending the Evaluation System

The evaluation system can be extended by:

1. Adding new metrics in the `evaluate_rag_system` function in `rag/evaluation.py`
2. Creating new visualization functions in `rag/visualize_results.py`
3. Modifying the quality criteria in the `filter_qa_pairs` function 