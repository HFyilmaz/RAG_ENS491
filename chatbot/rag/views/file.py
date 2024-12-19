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
    # Get the list of files uploaded
    files = request.FILES.getlist('file')
    
    if not files:
        return Response({"error": "No files provided"}, status=status.HTTP_400_BAD_REQUEST)

    errors = []
    success_files = []
    error_files = []

    for file in files:
        filename = file.name
        uploaded_file = UploadedFile(file=file)

        # Create a form instance for each file
        form = FileUploadForm(data=request.POST, files={'file': file})
        try:
            # Save the file instance
            uploaded_file.save()
            success_files.append(filename)
        except Exception as e:
            error_files.append(filename)

    
    # Run the populator function if at least one file is successfully uploaded
    if len(success_files) > 0:
        success_files = ",".join(success_files)

        is_vectordb_changed = populator()  # Run your database population logic
        ## SYNC RagFile model to update the database as we add new data to the folder
        RagFile.sync_rag_files(request.user)


        if is_vectordb_changed:
            return Response(
            {"message": f"{success_files} files uploaded successfully.",
            "error_files": f"{error_files}"},
            status=status.HTTP_201_CREATED
        )

        else:
             return Response({"message": "The files are already in the vector database."}, status=status.HTTP_400_BAD_REQUEST)
        
    else:

        return Response({"message": "Files could not be uploaded", "error_files": error_files}, status=status.HTTP_400_BAD_REQUEST)