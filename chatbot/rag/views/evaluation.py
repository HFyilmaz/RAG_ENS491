import os
import json
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from ..models import RagFile
from ..evaluation import (
    generate_qa_pairs,
    filter_qa_pairs,
    evaluate_rag_system,
    QA_PAIRS_PATH,
    FILTERED_QA_PAIRS_PATH,
    EVALUATION_RESULTS_PATH
)
from ..llm_model import query_llm

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_evaluation_data(request):
    """Get all evaluation data: QA pairs, filtered pairs, and evaluation results."""
    data = {
        "qa_pairs": [],
        "filtered_qa_pairs": [],
        "results": None
    }
    
    # Load QA pairs if they exist
    if os.path.exists(QA_PAIRS_PATH):
        with open(QA_PAIRS_PATH, 'r') as f:
            data["qa_pairs"] = json.load(f)
    
    # Load filtered QA pairs if they exist
    if os.path.exists(FILTERED_QA_PAIRS_PATH):
        with open(FILTERED_QA_PAIRS_PATH, 'r') as f:
            data["filtered_qa_pairs"] = json.load(f)
    
    # Load evaluation results if they exist
    if os.path.exists(EVALUATION_RESULTS_PATH):
        with open(EVALUATION_RESULTS_PATH, 'r') as f:
            data["results"] = json.load(f)
    
    return JsonResponse(data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_evaluation_qa_pairs(request):
    """Generate QA pairs for evaluation."""
    # Extract parameters from request
    total_pairs = int(request.data.get('total_pairs', 10))
    document_ids = request.data.get('document_ids', None)
    
    # Convert document IDs to document sources if provided
    document_sources = None
    if document_ids:
        try:
            # Get file paths for the specified document IDs
            rag_files = RagFile.objects.filter(id__in=document_ids)
            if not rag_files.exists():
                return JsonResponse({"status": "error", "message": "No documents found with the specified IDs"}, status=400)
            
            document_sources = []
            for rag_file in rag_files:
                file_path = os.path.join(settings.DATA_PATH, rag_file.file_name)
                if os.path.exists(file_path):
                    document_sources.append(file_path)
                else:
                    return JsonResponse({
                        "status": "error", 
                        "message": f"File not found in data directory: {rag_file.file_name}"
                    }, status=400)
        except Exception as e:
            return JsonResponse({"status": "error", "message": f"Error retrieving documents: {str(e)}"}, status=400)
    
    # Generate QA pairs
    qa_pairs = generate_qa_pairs(total_pairs=total_pairs, document_sources=document_sources)
    
    return JsonResponse({
        "status": "success", 
        "message": f"Generated {len(qa_pairs)} QA pairs" + (f" from {len(document_sources)} documents" if document_sources else " randomly from all documents"), 
        "qa_pairs": qa_pairs
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def filter_evaluation_qa_pairs(request):
    """Filter QA pairs based on quality criteria."""
    # Check if QA pairs exist
    if not os.path.exists(QA_PAIRS_PATH):
        return JsonResponse({"status": "error", "message": "No QA pairs found. Generate QA pairs first."}, status=400)
    
    # Load QA pairs
    with open(QA_PAIRS_PATH, 'r') as f:
        qa_pairs = json.load(f)
    
    # Filter QA pairs
    filtered_pairs = filter_qa_pairs(qa_pairs)
    
    return JsonResponse({
        "status": "success", 
        "message": f"Successfully filtered QA pairs", 
        "filtered_pairs_count": len(filtered_pairs),
        "filtered_qa_pairs": filtered_pairs,
    })

''' TODO:
    - Ensure that it calls the evaluation function in evaluation.py based on the id of the QA pair
'''
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def evaluate_qa_pair(request):
    """Evaluate a single QA pair."""
    # Extract parameters from request
    question = request.data.get('question')
    reference_answer = request.data.get('reference_answer')
    qa_id = request.data.get('id')  # Get the QA pair ID if provided
    
    if not question or not reference_answer:
        return JsonResponse({"status": "error", "message": "Question and reference answer are required"}, status=400)
    
    # Query the RAG system with the question
    rag_response = query_llm(question, [])
    rag_answer = rag_response["response_text"]
    retrieved_sources = rag_response["sources"]
    
    # Evaluate the response using the same method as in evaluate_rag_system
    # But simplified for a single QA pair
    from langchain_core.prompts import ChatPromptTemplate
    from ..evaluation import llm_ollama
    
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
    
    # Calculate overall score if not present
    if 'overall' not in scores and len(scores) > 0:
        scores['overall'] = sum(scores.values()) / len(scores)
    
    result = {
        "id": qa_id,  # Include the QA pair ID in the result
        "question": question,
        "reference_answer": reference_answer,
        "rag_answer": rag_answer,
        "retrieved_sources": retrieved_sources,
        "scores": scores,
        "evaluation": evaluation
    }
    
    return JsonResponse({"status": "success", "result": result})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def evaluate_all_filtered_qa_pairs(request):
    """Evaluate all filtered QA pairs."""
    # Check if filtered QA pairs exist
    if not os.path.exists(FILTERED_QA_PAIRS_PATH):
        return JsonResponse({"status": "error", "message": "No filtered QA pairs found. Filter QA pairs first."}, status=400)
    
    # Get filename from request if provided
    filename = request.data.get('filename', None)
    
    # Load filtered QA pairs
    with open(FILTERED_QA_PAIRS_PATH, 'r') as f:
        filtered_pairs = json.load(f)
    
    # Evaluate RAG system
    results = evaluate_rag_system(filtered_pairs, filename)
    
    return JsonResponse({
        "status": "success", 
        "message": f"Evaluation is complete!", 
        "results": results
    }) 