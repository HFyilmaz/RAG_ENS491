import os
import json
import time
import logging
from typing import List, Dict, Any, Tuple, Optional

from django.conf import settings
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma

from .vectordb import get_embedding_function_ollama, split_documents, load_documents
from .llm_model import get_context, query_llm

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the LLM
llm_ollama = OllamaLLM(model="llama3.1", base_url="http://host.docker.internal:11434")

# Paths for storing evaluation data
EVAL_DIR = os.path.join(settings.BASE_DIR, "rag", "evaluation_data")
QA_PAIRS_PATH = os.path.join(EVAL_DIR, "qa_pairs.json")
FILTERED_QA_PAIRS_PATH = os.path.join(EVAL_DIR, "filtered_qa_pairs.json")
EVALUATION_RESULTS_PATH = os.path.join(EVAL_DIR, "evaluation_results.json")

# Ensure evaluation directory exists
os.makedirs(EVAL_DIR, exist_ok=True)

def generate_qa_pairs(total_pairs: int = 10, document_sources: List[str] = None) -> List[Dict[str, Any]]:
    """
    Generate question-answer pairs from the document chunks in the database.
    
    Args:
        total_pairs: Total number of QA pairs to generate
        document_sources: Optional list of document sources to filter by. If None, all documents are used.
        
    Returns:
        List of dictionaries containing question, answer, and source metadata
    """
    if document_sources:
        logger.info(f"Generating {total_pairs} QA pairs from {len(document_sources)} specified documents...")
    else:
        logger.info(f"Generating {total_pairs} QA pairs randomly from all available documents...")
    
    # Load documents and split into chunks
    documents = load_documents()
    chunks = split_documents(documents)
    
    qa_pairs = []
    
    # Group chunks by document source
    chunks_by_source = {}
    for chunk in chunks:
        source = chunk.metadata.get("source", "unknown")
        if source not in chunks_by_source:
            chunks_by_source[source] = []
        chunks_by_source[source].append(chunk)
    
    # Filter sources if document_sources is provided
    if document_sources:
        filtered_sources = {source: chunks for source, chunks in chunks_by_source.items() 
                           if source in document_sources}
        if not filtered_sources:
            logger.warning(f"None of the specified document sources were found in the database.")
            return []
        chunks_by_source = filtered_sources
    
    # Initialize ID counter
    qa_pair_id = 1
    
    # Get all available sources
    available_sources = list(chunks_by_source.keys())
    if not available_sources:
        logger.warning("No document sources available.")
        return []
    
    import random
    
    # Generate the requested number of QA pairs
    pairs_generated = 0
    failed_to_generate = 0
    while pairs_generated < total_pairs and available_sources:

        if failed_to_generate > 3:
            logger.warning("Failed to generate 3 QA pairs in a row. Exiting.")
            break
        # Select a random source if document_sources is not specified
        # Otherwise, distribute pairs evenly among the specified sources
        if document_sources:
            # Distribute evenly among specified sources
            source_index = pairs_generated % len(available_sources)
            source = available_sources[source_index]
        else:
            # Select a random source for each pair
            source = random.choice(available_sources)
        
        doc_chunks = chunks_by_source[source]
        if not doc_chunks:
            # If this source has no chunks, remove it and continue
            available_sources.remove(source)
            continue
            
        # Select a random chunk from the source
        chunk = random.choice(doc_chunks)
        
        # Create QA generation prompt
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", """Generate a challenging but answerable question-answer pair based on the following text. 
            The question should:
            1. Be specific and focused on factual information in the text
            2. Require a detailed understanding of the content
            3. Not be answerable with general knowledge alone
            
            Format your response exactly as:
            QUESTION: [your generated question]
            ANSWER: [comprehensive answer based strictly on the provided text]"""),
            ("human", f"TEXT: {chunk.page_content}")
        ])
        
        try:
            # Generate QA pair
            result = llm_ollama.invoke(qa_prompt.format())
            
            # Parse the QA pair from the result
            lines = result.strip().split('\n')
            question = ""
            answer = ""
            
            # Extract question and answer
            for line in lines:
                if line.startswith("QUESTION:"):
                    question = line.replace("QUESTION:", "").strip()
                elif line.startswith("ANSWER:"):
                    answer = line.replace("ANSWER:", "").strip()
                # Handle multi-line answers
                elif question and answer:
                    answer += " " + line.strip()
            
            if question and answer:
                qa_pairs.append({
                    "id": qa_pair_id,
                    "question": question,
                    "answer": answer,
                    "source": source,
                    "page": chunk.metadata.get("page", 0),
                    "chunk_id": chunk.metadata.get("id", ""),
                    "chunk_content": chunk.page_content
                })
                logger.info(f"Generated QA pair {qa_pair_id}: {question[:50]}...")
                qa_pair_id += 1  # Increment ID counter
                pairs_generated += 1  # Increment pairs counter
                failed_to_generate = 0
            else:
                logger.warning(f"Failed to parse QA pair from: {result[:100]}...")
        
        except Exception as e:
            logger.error(f"Error generating QA pair: {str(e)}")
            failed_to_generate += 1
    # Save QA pairs to file
    with open(QA_PAIRS_PATH, 'w') as f:
        json.dump(qa_pairs, f, indent=2)
    
    logger.info(f"Generated {len(qa_pairs)} QA pairs in total")
    return qa_pairs

def filter_qa_pairs(qa_pairs: List[Dict[str, Any]], min_quality_score: float = 0.7) -> List[Dict[str, Any]]:
    """
    Filter QA pairs based on quality criteria using an LLM as judge.
    
    Args:
        qa_pairs: List of QA pairs to filter
        min_quality_score: Minimum quality score (0-1) for a QA pair to pass the filter
        
    Returns:
        Filtered list of QA pairs with quality scores
    """
    logger.info(f"Filtering {len(qa_pairs)} QA pairs...")
    
    filtered_pairs = []
    
    for i, qa_pair in enumerate(qa_pairs):
        question = qa_pair["question"]
        reference_answer = qa_pair["answer"]
        context = qa_pair["chunk_content"]
        qa_id = qa_pair.get("id", i+1)  # Use existing ID or fallback to index+1
        
        logger.info(f"Evaluating quality of QA pair {qa_id}: {question[:50]}...")
        
        # Create filter criteria prompt
        filter_prompt = ChatPromptTemplate.from_messages([
            ("system", """Evaluate the quality of this question-answer pair based on the following criteria:
            1. Groundedness: Does the answer strictly use information from the context? (0-10)
            2. Relevance: Is the question relevant to the main topics in the context? (0-10)
            3. Specificity: Is the question specific rather than general? (0-10)
            4. Complexity: Does the question require reasoning rather than just fact retrieval? (0-10)
            5. Clarity: Is the question clearly formulated? (0-10)
            
            Format your response exactly as follows:
            GROUNDEDNESS: [score]
            RELEVANCE: [score]
            SPECIFICITY: [score]
            COMPLEXITY: [score]
            CLARITY: [score]
            OVERALL: [average score]
            REASONING: [brief explanation of your evaluation]"""),
            ("human", f"CONTEXT: {context}\n\nQUESTION: {question}\n\nREFERENCE ANSWER: {reference_answer}")
        ])
        
        try:
            # Get quality evaluation
            result = llm_ollama.invoke(filter_prompt.format())
            
            # Parse scores
            scores = {}
            lines = result.strip().split('\n')
            
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    
                    if key in ['groundedness', 'relevance', 'specificity', 'complexity', 'clarity', 'overall']:
                        try:
                            scores[key] = float(value.strip()) / 10  # Convert to 0-1 scale
                        except ValueError:
                            scores[key] = 0.0
            
            # Check if we have an overall score
            if 'overall' not in scores and len(scores) > 0:
                scores['overall'] = sum(scores.values()) / len(scores)
            
            # Add quality scores to the QA pair
            qa_pair['quality_scores'] = scores
            qa_pair['quality_evaluation'] = result
            
            # Filter based on quality
            if scores.get('overall', 0) >= min_quality_score:
                filtered_pairs.append(qa_pair)
                logger.info(f"QA pair {qa_id} passed filter ({scores.get('overall', 0):.2f}): {question[:50]}...")
            else:
                logger.info(f"QA pair {qa_id} failed filter ({scores.get('overall', 0):.2f}): {question[:50]}...")
                
        except Exception as e:
            logger.error(f"Error filtering QA pair {qa_id}: {str(e)}")
    
    # Save filtered QA pairs to file
    with open(FILTERED_QA_PAIRS_PATH, 'w') as f:
        json.dump(filtered_pairs, f, indent=2)
    
    logger.info(f"{len(filtered_pairs)} QA pairs passed quality filtering")
    return filtered_pairs

def evaluate_rag_system(qa_pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluate the RAG system using filtered QA pairs.
    
    Args:
        qa_pairs: List of high-quality QA pairs to use for evaluation
        
    Returns:
        Dictionary with evaluation results
    """
    logger.info(f"Evaluating RAG system with {len(qa_pairs)} QA pairs...")
    
    results = {
        "qa_results": [],
        "metrics": {
            "relevance": 0.0,
            "faithfulness": 0.0,
            "context_precision": 0.0,
            "answer_correctness": 0.0,
            "overall_score": 0.0
        }
    }
    
    for i, qa_pair in enumerate(qa_pairs):
        question = qa_pair["question"]
        reference_answer = qa_pair["answer"]
        qa_id = qa_pair.get("id", i+1)  # Use existing ID or fallback to index+1
        
        logger.info(f"Evaluating question {i+1}/{len(qa_pairs)} (ID: {qa_id}): {question[:50]}...")
        
        try:
            # Query the RAG system with the question
            rag_response = query_llm(question, [])
            rag_answer = rag_response["response_text"]
            retrieved_sources = rag_response["sources"]
            
            # Create evaluation prompt
            eval_prompt = ChatPromptTemplate.from_messages([
                ("system", """Evaluate the RAG system's answer based on the following criteria:
                1. Relevance (0-10): How relevant is the generated answer to the question?
                2. Faithfulness (0-10): Does the answer contain hallucinations or make claims not supported by the retrieved context?
                3. Context Precision (0-10): Were the retrieved contexts helpful and necessary for answering the question?
                4. Answer Correctness (0-10): How correct is the generated answer compared to the reference answer?
                
                Format your response exactly as follows:
                RELEVANCE: [score]
                FAITHFULNESS: [score]
                CONTEXT_PRECISION: [score]
                ANSWER_CORRECTNESS: [score]
                OVERALL: [average score]
                REASONING: [brief explanation of your evaluation]"""),
                ("human", f"QUESTION: {question}\n\nRAG SYSTEM ANSWER: {rag_answer}\n\nREFERENCE ANSWER: {reference_answer}")
            ])
            
            # Get evaluation results
            evaluation = llm_ollama.invoke(eval_prompt.format())
            
            # Parse scores
            scores = {}
            lines = evaluation.strip().split('\n')
            
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    
                    if key in ['relevance', 'faithfulness', 'context_precision', 'answer_correctness', 'overall']:
                        try:
                            scores[key] = float(value.strip()) / 10  # Convert to 0-1 scale
                        except ValueError:
                            scores[key] = 0.0
            
            # Check if we have an overall score
            if 'overall' not in scores and len(scores) > 0:
                scores['overall'] = sum(scores.values()) / len(scores)
            
            # Add evaluation result
            result = {
                "id": qa_id,
                "question": question,
                "reference_answer": reference_answer,
                "rag_answer": rag_answer,
                "retrieved_sources": retrieved_sources,
                "expected_source": qa_pair["chunk_id"],
                "scores": scores,
                "evaluation": evaluation
            }
            
            results["qa_results"].append(result)
            
            # Update metrics
            for metric in ["relevance", "faithfulness", "context_precision", "answer_correctness", "overall"]:
                results["metrics"][metric] += scores.get(metric, 0)
            
            logger.info(f"Evaluated QA pair {qa_id} - Overall score: {scores.get('overall', 0):.2f}")
            
        except Exception as e:
            logger.error(f"Error evaluating QA pair {qa_id}: {str(e)}")
    
    # Calculate average metrics
    num_pairs = len(results["qa_results"])
    if num_pairs > 0:
        for metric in results["metrics"]:
            results["metrics"][metric] /= num_pairs
    
    # Save evaluation results to file
    with open(EVALUATION_RESULTS_PATH, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Evaluation complete. Overall score: {results['metrics']['overall_score']:.2f}")
    return results

def load_or_generate_qa_pairs(force_regenerate: bool = False, total_pairs: int = 10, document_sources: List[str] = None) -> List[Dict[str, Any]]:
    """Load existing QA pairs from file or generate new ones if needed"""
    if not force_regenerate and os.path.exists(QA_PAIRS_PATH) and document_sources is None:
        with open(QA_PAIRS_PATH, 'r') as f:
            return json.load(f)
    return generate_qa_pairs(total_pairs, document_sources)

def load_or_filter_qa_pairs(qa_pairs: List[Dict[str, Any]], force_refilter: bool = False) -> List[Dict[str, Any]]:
    """Load existing filtered QA pairs from file or filter again if needed"""
    if not force_refilter and os.path.exists(FILTERED_QA_PAIRS_PATH):
        with open(FILTERED_QA_PAIRS_PATH, 'r') as f:
            return json.load(f)
    return filter_qa_pairs(qa_pairs)

def run_full_evaluation(
    force_regenerate_qa: bool = False,
    force_refilter_qa: bool = False,
    total_pairs: int = 10,
    min_quality_score: float = 0.7,
    document_sources: List[str] = None
) -> Dict[str, Any]:
    """
    Run the full evaluation pipeline, from generating QA pairs to evaluating the RAG system.
    
    Args:
        force_regenerate_qa: Whether to regenerate QA pairs even if they already exist
        force_refilter_qa: Whether to refilter QA pairs even if filtered pairs already exist
        total_pairs: Total number of QA pairs to generate
        min_quality_score: Minimum quality score (0-1) for a QA pair to pass the filter
        document_sources: Optional list of document sources to filter by. If None, all documents are used.
        
    Returns:
        Dictionary with evaluation results
    """
    # Step 1: Generate or load QA pairs
    qa_pairs = load_or_generate_qa_pairs(force_regenerate_qa, total_pairs, document_sources)
    
    # Step 2: Filter or load filtered QA pairs
    filtered_pairs = load_or_filter_qa_pairs(qa_pairs, force_refilter_qa)
    
    # Step 3: Evaluate RAG system
    results = evaluate_rag_system(filtered_pairs)
    
    return results 