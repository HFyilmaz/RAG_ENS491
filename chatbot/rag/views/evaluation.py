import os
import json
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import time

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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def evaluate_qa_pair(request):
    """Evaluate one or more QA pairs by ID from filtered QA pairs."""
    # Extract QA pair ID(s) from request
    qa_ids = request.data.get('id')
    
    # Handle both single ID and list of IDs
    if not qa_ids:
        return JsonResponse({"status": "error", "message": "QA pair ID(s) are required"}, status=400)
    
    # Convert single ID to list for consistent processing
    if not isinstance(qa_ids, list):
        qa_ids = [qa_ids]
    
    # Check if filtered QA pairs exist
    if not os.path.exists(FILTERED_QA_PAIRS_PATH):
        return JsonResponse({"status": "error", "message": "No filtered QA pairs found. Filter QA pairs first."}, status=400)
    
    # Load filtered QA pairs
    with open(FILTERED_QA_PAIRS_PATH, 'r') as f:
        filtered_pairs = json.load(f)
    
    # Find the QA pairs with the given IDs
    selected_pairs = []
    not_found_ids = []
    
    for qa_id in qa_ids:
        qa_pair = None
        for pair in filtered_pairs:
            if str(pair.get('id')) == str(qa_id):
                qa_pair = pair
                selected_pairs.append(qa_pair)
                break
        
        if not qa_pair:
            not_found_ids.append(qa_id)
    
    if not selected_pairs:
        return JsonResponse({"status": "error", "message": f"None of the requested QA pair IDs were found in filtered QA pairs", "not_found_ids": not_found_ids}, status=404)
    
    # Generate a filename with the QA pair IDs
    id_string = "_".join(str(qa_id) for qa_id in qa_ids[:3])
    if len(qa_ids) > 3:
        id_string += f"_and_{len(qa_ids) - 3}_more"
    
    filename = f"qa_evaluation_{id_string}_{int(time.time())}.json"
    
    # Evaluate the QA pairs
    results = evaluate_rag_system(selected_pairs, filename)
    
    # Include information about not found IDs if any
    response_data = {
        "status": "success", 
        "message": f"Evaluation of {len(selected_pairs)} QA pair(s) is complete!", 
        "results": results
    }
    
    if not_found_ids:
        response_data["warning"] = f"{len(not_found_ids)} QA pair ID(s) not found"
        response_data["not_found_ids"] = not_found_ids
    
    return JsonResponse(response_data)

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