from django.shortcuts import render, redirect
from .forms import FileUploadForm
from .models import UploadedFile
from .vectordb import populator
import os
from django.conf import settings

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

@api_view(['GET', 'POST'])
def upload_file(request):
    if request.method == 'POST':
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

            return redirect('rag:populate_database')
        else:
            return Response({"errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)
    elif request.method == 'GET':
        form = FileUploadForm()
        return render(request, 'rag/upload_file.html', {'form': form})

    

@api_view(['GET'])
def populate_database(request):
    message = populator()
    return render(request, 'rag/populate_database.html', {'message': message})
    
