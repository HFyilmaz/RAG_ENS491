from django.shortcuts import render, redirect
from ..forms import FileUploadForm
from ..models import UploadedFile
from ..models import RagFile 
from ..vectordb import populator, delete_file_from_chroma
from ..serializers import RagFileSerializer
from ..permissions import IsAdmin

import os
from django.conf import settings
from django.shortcuts import get_object_or_404

from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from matching.elastic_search import setup_elasticsearch, index_pdf_content, delete_file_from_elasticsearch, file_exists_in_elasticsearch
import pdfplumber

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])
def delete_rag_file(request, rag_file_id):
    try:
        # Find the RagFile object by its ID
        rag_file = RagFile.objects.get(id=rag_file_id)
        
        # Delete it from the folder
        RagFile.delete_rag_file_from_folder(rag_file.file_name)

        # Delete from vector database and elasticsearch
        chroma_deleted = delete_file_from_chroma(rag_file.file_name)
        es_deleted = delete_file_from_elasticsearch(rag_file.file_name)

        if not chroma_deleted or not es_deleted:
            return Response(
                {"error": "Error deleting from databases"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Delete the file record
        rag_file.delete()

        return Response({"message": f"File {rag_file.file_name} deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

    except RagFile.DoesNotExist:
        return Response({"error": "File not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": f"Error deleting file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def get_rag_files(request):
    # Query all RagFile objects
    rag_files = RagFile.objects.all()

    # Serialize the data
    serializer = RagFileSerializer(rag_files, many=True)

    # Return the serialized data
    return Response(serializer.data, status=status.HTTP_200_OK)



@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin]) 
def upload_file(request):
    # Ensure the rag_database directory exists
    os.makedirs(settings.DATA_PATH, exist_ok=True)
    
    # Get the list of files uploaded
    files = request.FILES.getlist('file')
    
    if not files:
        return Response({"error": "No files provided"}, status=status.HTTP_400_BAD_REQUEST)

    errors = []
    success_files = []
    existing_files = []
    error_files = []

    # Ensure Elasticsearch is set up
    if not setup_elasticsearch():
        return Response({
            "error": "Failed to setup Elasticsearch"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    for file in files:
        filename = file.name
        try:
            # Check if file already exists in Elasticsearch
            if file_exists_in_elasticsearch(filename):
                print(f"File {filename} already exists in Elasticsearch, skipping")
                existing_files.append(filename)
                continue

            # Save the file to the rag_database directory
            file_path = os.path.join(settings.DATA_PATH, filename)
            with open(file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            success_files.append(filename)
            
            # Index the file in Elasticsearch
            try:
                with pdfplumber.open(file_path) as pdf:
                    for i, page in enumerate(pdf.pages):
                        page_text = page.extract_text()
                        if page_text:
                            index_pdf_content(filename, i + 1, page_text)
            except Exception as e:
                print(f"Error indexing {filename}: {e}")
                error_files.append(filename)
                
        except Exception as e:
            error_files.append(filename)
            print(f"Error processing {filename}: {e}")

    # Prepare response message
    if len(success_files) > 0 or len(existing_files) > 0:
        response_message = []
        if success_files:
            response_message.append(f"Successfully uploaded and indexed: {', '.join(success_files)}")
        if existing_files:
            response_message.append(f"Already indexed (skipped): {', '.join(existing_files)}")
        
        # Run vector database population only if there are new files
        if success_files:
            is_vectordb_changed = populator()
            try:
                # Sync RagFile model
                RagFile.sync_rag_files(request.user)
            except Exception as e:
                return Response({
                    "message": "Files uploaded but model sync failed",
                    "error": str(e),
                    "error_files": error_files
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            "message": " | ".join(response_message),
            "success_files": success_files,
            "existing_files": existing_files,
            "error_files": error_files
        }, status=status.HTTP_200_OK)
    
    elif error_files:
        return Response({
            "message": "All files failed to upload",
            "error_files": error_files
        }, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response({
            "message": "No files were processed",
        }, status=status.HTTP_400_BAD_REQUEST)