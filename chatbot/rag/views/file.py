from django.shortcuts import render, redirect
from ..forms import FileUploadForm
from ..models import UploadedFile
from ..vectordb import populator
import os
from django.conf import settings

from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

@api_view(['POST'])
@permission_classes([IsAuthenticated]) 
def upload_file(request):
    # Handle file upload
    form = FileUploadForm(request.POST, request.FILES)
    if form.is_valid():
        form.save()

        # Save the files to the data directory
        data_dir = settings.DATA_PATH
        for file in request.FILES.getlist('file'):
            destination = os.path.join(data_dir, file.name)

            # Ensure the `data/` directory exists
            os.makedirs(data_dir, exist_ok=True)

            # Save the file
            with open(destination, 'wb+') as dest:
                for chunk in file.chunks():
                    dest.write(chunk)

        # Populate database from "data" folder
        message = populator()

        return Response({"message": message}, status=status.HTTP_201_CREATED)
    else:
        return Response({"errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)
    