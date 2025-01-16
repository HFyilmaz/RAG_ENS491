from django.shortcuts import render, redirect
from ..forms import FileUploadForm
from ..models import UploadedFile
from ..models import RagFile 
from ..vectordb import populator
from ..serializers import RagFileSerializer
from ..permissions import IsAdmin, IsUser

import os
from django.conf import settings
from django.shortcuts import get_object_or_404

from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from matching.elastic_search import setup_elasticsearch, index_pdf_content, clear_index
import pdfplumber

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])
def delete_rag_file(request, rag_file_id):
    try:
        # Find the RagFile object by its ID
        rag_file = RagFile.objects.get(id=rag_file_id)
        # Delete it from the folder
        RagFile.delete_rag_file_from_folder(rag_file.file_name)

        # Delete the file record
        rag_file.delete()

        # TODO: DELETE ALSO FROM THE VECTOR DATABASE

        return Response({"message": f"File {rag_file.file_name} deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

    except RagFile.DoesNotExist:
        return Response({"error": "File not found."}, status=status.HTTP_404_NOT_FOUND)



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
    error_files = []

    # Ensure Elasticsearch is set up
    if not setup_elasticsearch():
        return Response({
            "error": "Failed to setup Elasticsearch"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    for file in files:
        filename = file.name
        try:
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

    if len(success_files) > 0:
        success_files_str = ",".join(success_files)
        
        # Run vector database population
        is_vectordb_changed = populator()
        
        try:
            # Sync RagFile model
            RagFile.sync_rag_files(request.user)

            if is_vectordb_changed:
                return Response({
                    "message": f"{success_files_str} files uploaded successfully and indexed.",
                    "error_files": error_files
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    "message": "Files are already in the vector database but were indexed for search.",
                    "error_files": error_files
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            return Response({
                "message": "Files uploaded but indexing failed",
                "error": str(e),
                "error_files": error_files
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        return Response({
            "message": "Files could not be uploaded", 
            "error_files": error_files
        }, status=status.HTTP_400_BAD_REQUEST)