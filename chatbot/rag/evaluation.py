import os
import json
import time
import logging
from typing import List, Dict, Any, Tuple, Optional

from django.conf import settings
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.schema import SystemMessage 
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
            ("system", """
            Your task is to write a factoid question and an answer given a context.
            Your factoid question should be answerable with a specific, concise piece of factual information from the context.
            Your factoid question should be formulated in the same style as questions users could ask in a search engine.
            This means that your factoid question MUST NOT mention something like "according to the passage" or "context".

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

def filter_qa_pairs(qa_pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter QA pairs based on quality criteria using an LLM as judge.
    QA pairs must score at least 4 out of 5 on both groundedness and standalone criteria.
    
    Args:
        qa_pairs: List of QA pairs to filter
        
    Returns:
        Filtered list of QA pairs with quality scores
    """
    logger.info(f"Filtering {len(qa_pairs)} QA pairs...")
    
    filtered_pairs = []
    
    question_groundedness_critique_prompt = ChatPromptTemplate.from_messages([
        ("system", """
        You will be given a context and a question.
        Your task is to provide a 'total rating' scoring how well one can answer the given question unambiguously with the given context.
        Give your answer on a scale of 1 to 5, where 1 means that the question is not answerable at all given the context, and 5 means that the question is clearly and unambiguously answerable with the context.

        Provide your answer as follows:

        Answer:::
        Evaluation: (your rationale for the rating, as a text)
        Total rating: (your rating, as a number between 1 and 5)
        
        You MUST provide values for 'Evaluation:' and 'Total rating:' in your answer.

        Now here are the question and context.

        Question: {question}
        Context: {context}
        Answer:::
        """),
        ("human", "QUESTION: {question}\n\nANSWER: {answer}")
    ])

    question_standalone_critique_prompt = ChatPromptTemplate.from_messages([
        ("system", """
        You will be given a question.
        Your task is to provide a 'total rating' representing how context-independent this question is.
        Give your answer on a scale of 1 to 5, where 1 means that the question depends on additional information to be understood, and 5 means that the question makes sense by itself.
        For instance, if the question refers to a particular setting, like 'in the context' or 'in the document', the rating must be 1.
        The questions can contain obscure technical nouns or acronyms like Gradio, Hub, Hugging Face or Space and still be a 5: it must simply be clear to an operator with access to documentation what the question is about.

        For instance, "What is the name of the checkpoint from which the ViT model is imported?" should receive a 1, since there is an implicit mention of a context, thus the question is not independent from the context.

        Provide your answer as follows:

        Answer:::
        Evaluation: (your rationale for the rating, as a text)
        Total rating: (your rating, as a number between 1 and 5)

        You MUST provide values for 'Evaluation:' and 'Total rating:' in your answer.

        Now here is the question.

        Question: {question}
        Answer::: 
        """),
        ("human", "QUESTION: {question}\n\nANSWER: {answer}")
    ])

    for i, qa_pair in enumerate(qa_pairs):
        question = qa_pair["question"]
        reference_answer = qa_pair["answer"]
        context = qa_pair["chunk_content"]
        source_file = qa_pair["source"]
        source_page = qa_pair["page"]
        qa_id = qa_pair.get("id", i+1)
        
        logger.info(f"Evaluating quality of QA pair {qa_id}: {question[:50]}...")
        
        try:
            # Evaluate groundedness
            groundedness_prompt = question_groundedness_critique_prompt.format(
                question=question,
                context=context,
                answer=reference_answer
            )
            groundedness_result = llm_ollama.invoke(groundedness_prompt)
            
            # Evaluate standalone quality
            standalone_prompt = question_standalone_critique_prompt.format(
                question=question,
                answer=reference_answer
            )
            standalone_result = llm_ollama.invoke(standalone_prompt)
            
            # Parse groundedness evaluation
            groundedness_evaluation = ""
            groundedness_rating = 0
            
            for line in groundedness_result.strip().split('\n'):
                if line.lower().startswith("evaluation:"):
                    groundedness_evaluation = line.split(":", 1)[1].strip()
                elif line.lower().startswith("total rating:"):
                    try:
                        groundedness_rating = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        groundedness_rating = 0
            
            # Parse standalone evaluation
            standalone_evaluation = ""
            standalone_rating = 0
            
            for line in standalone_result.strip().split('\n'):
                if line.lower().startswith("evaluation:"):
                    standalone_evaluation = line.split(":", 1)[1].strip()
                elif line.lower().startswith("total rating:"):
                    try:
                        standalone_rating = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        standalone_rating = 0
            
            # Store evaluations and ratings in the QA pair
            qa_pair['groundedness'] = {
                'evaluation': groundedness_evaluation,
                'rating': groundedness_rating
            }
            qa_pair['standalone'] = {
                'evaluation': standalone_evaluation,
                'rating': standalone_rating
            }
            
            qa_pair['passed_filter'] = groundedness_rating >= 4 and standalone_rating >= 4
            filtered_pairs.append(qa_pair)

        except Exception as e:
            logger.error(f"Error filtering QA pair {qa_id}: {str(e)}")
    
    with open(FILTERED_QA_PAIRS_PATH, 'w') as f:
        json.dump(filtered_pairs, f, indent=2)
    
    return filtered_pairs

def get_unique_evaluation_filename(provided_name=None):
    """
    Generate a unique filename for evaluation results.
    
    Args:
        provided_name: Optional name provided by the user
        
    Returns:
        A unique filename for the evaluation results
    """
    if provided_name:
        # If a name is provided, ensure it has the .json extension
        if not provided_name.endswith('.json'):
            provided_name += '.json'
        
        # Check if a file with this name already exists
        full_path = os.path.join(EVAL_DIR, provided_name)
        if not os.path.exists(full_path):
            return provided_name
        else:
            logger.warning(f"File {provided_name} already exists. Generating a unique name instead.")
    
    # If no name is provided or the provided name already exists, generate a unique name
    # Count the number of existing evaluation result files
    existing_files = [f for f in os.listdir(EVAL_DIR) if f.startswith('evaluation_results_') and f.endswith('.json')]
    
    # Find the highest number used so far
    highest_num = 0
    for file in existing_files:
        try:
            # Extract the number from filenames like "evaluation_results_1.json"
            num = int(file.replace('evaluation_results_', '').replace('.json', ''))
            highest_num = max(highest_num, num)
        except ValueError:
            continue
    
    # Generate a new filename with the next number
    return f"evaluation_results_{highest_num + 1}.json"

def evaluate_rag_system(qa_pairs: List[Dict[str, Any]], filename=None) -> Dict[str, Any]:
    """
    Evaluate the RAG system using filtered QA pairs.
    
    Args:
        qa_pairs: List of QA pairs that are tagged after filtering to use for evaluation
        filename: Optional filename for the evaluation results. If not provided, a unique name will be generated.
    Returns:
        Dictionary with evaluation results
    """
    # Filter QA pairs to only include those that passed the filter
    filtered_qa_pairs = [pair for pair in qa_pairs if pair.get('passed_filter', False)]
    
    logger.info(f"Evaluating RAG system with {len(filtered_qa_pairs)} QA pairs that passed filtering (out of {len(qa_pairs)} total pairs)...")
    
    # Define the evaluation prompt template
    evaluation_prompt = """###Task Description:
    An instruction (might include an Input inside it), a response to evaluate, a reference answer that gets a score of 5, and a score rubric representing a evaluation criteria are given.
    1. Write a detailed feedback that assess the quality of the response strictly based on the given score rubric, not evaluating in general.
    2. After writing a feedback, write a score that is an integer between 1 and 5. You should refer to the score rubric.
    3. The output format should look as follows: \"Feedback: {{write a feedback for criteria}} [RESULT] {{an integer number between 1 and 5}}\"
    4. Please do not generate any other opening, closing, and explanations. Be sure to include [RESULT] in your output.

    ###The instruction to evaluate:
    {instruction}

    ###Response to evaluate:
    {response}

    ###Reference Answer (Score 5):
    {reference_answer}

    ###Score Rubrics:
    [Is the response correct, accurate, and factual based on the reference answer?]
    Score 1: The response is completely incorrect, inaccurate, and/or not factual.
    Score 2: The response is mostly incorrect, inaccurate, and/or not factual.
    Score 3: The response is somewhat correct, accurate, and/or factual.
    Score 4: The response is mostly correct, accurate, and factual.
    Score 5: The response is completely correct, accurate, and factual.

    ###Feedback:"""

    evaluation_prompt_template = ChatPromptTemplate.from_messages([
        SystemMessage(content="You are a fair evaluator model."),
        HumanMessagePromptTemplate.from_template(evaluation_prompt)
    ])

    results = {
        "qa_pairs": [],
        "summary": {
            "total_pairs": len(qa_pairs),
            "filtered_pairs": len(filtered_qa_pairs),
            "average_score": 0,
            "scores_distribution": {}
        }
    }
    
    total_score = 0
    scores_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    for i, qa_pair in enumerate(filtered_qa_pairs):
        question = qa_pair["question"]
        reference_answer = qa_pair["answer"]
        qa_id = qa_pair.get("id", i+1)
        
        logger.info(f"Evaluating question {i+1}/{len(filtered_qa_pairs)} (ID: {qa_id}): {question[:50]}...")
        
        try:
            # Query the RAG system with the question
            rag_response = query_llm(question, [])
            rag_answer = rag_response["response_text"]
            retrieved_sources = rag_response["sources"]
            
            evaluation_prompt_formatted = evaluation_prompt_template.format(
                instruction=question,
                response=rag_answer,
                reference_answer=reference_answer
            )
            
            # Get evaluation results using the evaluation_prompt
            evaluation_result = llm_ollama.invoke(evaluation_prompt_formatted)
            
            # Parse the evaluation result
            feedback = ""
            score = 0
            
            # Extract feedback and score from the result
            result_text = evaluation_result.content if hasattr(evaluation_result, 'content') else str(evaluation_result)
            
            if "[RESULT]" in result_text:
                feedback, score_part = result_text.split("[RESULT]")
                feedback = feedback.replace("Feedback:", "").strip()
                try:
                    score = int(score_part.strip())
                    # Ensure score is between 1 and 5
                    score = max(1, min(5, score))
                except ValueError:
                    logger.warning(f"Could not parse score from evaluation result: {score_part}")
                    score = 0
            else:
                feedback = result_text
                logger.warning(f"Evaluation result did not contain [RESULT] marker: {result_text[:100]}...")
            
            # Update scores distribution
            if 1 <= score <= 5:
                scores_distribution[score] += 1
                total_score += score
            
            # Store evaluation results for this QA pair
            pair_result = {
                "id": qa_id,
                "question": question,
                "reference_answer": reference_answer,
                "rag_answer": rag_answer,
                "retrieved_sources": retrieved_sources,
                "evaluation": {
                    "feedback": feedback,
                    "score": score
                }
            }
            
            results["qa_pairs"].append(pair_result)
            logger.info(f"Evaluation score for QA pair {qa_id}: {score}/5")
            
        except Exception as e:
            logger.error(f"Error evaluating QA pair {qa_id}: {str(e)}")
            # Add failed evaluation to results
            pair_result = {
                "id": qa_id,
                "question": question,
                "reference_answer": reference_answer,
                "error": str(e)
            }
            results["qa_pairs"].append(pair_result)
    
    # Calculate average score
    if len(filtered_qa_pairs) > 0:
        results["summary"]["average_score"] = total_score / len(filtered_qa_pairs)
    
    # Add scores distribution to summary
    results["summary"]["scores_distribution"] = scores_distribution
    
    # Generate a unique filename if none is provided
    result_filename = get_unique_evaluation_filename(filename)
    result_filepath = os.path.join(EVAL_DIR, result_filename)
    
    # Save evaluation results to file
    with open(result_filepath, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Evaluation complete. Results saved to {result_filename}. Average score: {results['summary']['average_score']:.2f}/5")
    
    # Add the filename to the results
    results["filename"] = result_filename
    
    return results

def load_or_generate_qa_pairs(force_regenerate: bool = False, total_pairs: int = 10, document_sources: List[str] = None) -> List[Dict[str, Any]]:
    """Load existing QA pairs from file or generate new ones if needed"""
    if not force_regenerate and os.path.exists(QA_PAIRS_PATH) and document_sources is None:
        with open(QA_PAIRS_PATH, 'r') as f:
            return json.load(f)
    return generate_qa_pairs(total_pairs, document_sources)

def load_or_filter_qa_pairs(qa_pairs: List[Dict[str, Any]], force_refilter: bool = False) -> List[Dict[str, Any]]:
    """
    Load existing filtered QA pairs from file or filter again if needed.
    QA pairs are filtered based on groundedness and standalone ratings,
    requiring a score of at least 4 out of 5 for both criteria.
    """
    if not force_refilter and os.path.exists(FILTERED_QA_PAIRS_PATH):
        with open(FILTERED_QA_PAIRS_PATH, 'r') as f:
            return json.load(f)
    return filter_qa_pairs(qa_pairs)

def run_full_evaluation(
    force_regenerate_qa: bool = False,
    force_refilter_qa: bool = False,
    total_pairs: int = 10,
    document_sources: List[str] = None,
    filename: str = None
) -> Dict[str, Any]:
    """
    Run the full evaluation pipeline, from generating QA pairs to evaluating the RAG system.
    
    Args:
        force_regenerate_qa: Whether to regenerate QA pairs even if they already exist
        force_refilter_qa: Whether to refilter QA pairs even if filtered pairs already exist
        total_pairs: Total number of QA pairs to generate
        document_sources: Optional list of document sources to filter by. If None, all documents are used.
        filename: Optional filename for the evaluation results. If not provided, a unique name will be generated.
        
    Returns:
        Dictionary with evaluation results
    """
    # Step 1: Generate or load QA pairs
    qa_pairs = load_or_generate_qa_pairs(force_regenerate_qa, total_pairs, document_sources)
    
    # Step 2: Filter QA pairs based on quality
    filtered_qa_pairs = load_or_filter_qa_pairs(qa_pairs, force_refilter_qa)
    
    # Step 3: Evaluate RAG system using filtered QA pairs
    evaluation_results = evaluate_rag_system(filtered_qa_pairs, filename)
    
    return evaluation_results 