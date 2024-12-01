from django.shortcuts import render, redirect
from .forms import FileUploadForm
from .models import UploadedFile
from .vectordb import populator
import subprocess  # To call the populate_database script

import os
from django.conf import settings

def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()

            # Use DATA_PATH from settings.py
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
        form = FileUploadForm()

    return render(request, 'rag/upload_file.html', {'form': form})

def populate_database(request):
    message = populator()

    return render(request, 'rag/populate_database.html', {'message': message})
