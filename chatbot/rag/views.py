from django.shortcuts import render, redirect
from .forms import FileUploadForm
from .models import UploadedFile
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
    try:
        # Use the full path to `populate_database.py` in the `rag` directory
        script_path = os.path.join(settings.BASE_DIR, 'rag', 'populate_database.py')

        # Run the script using subprocess
        subprocess.run(['python', script_path], check=True)

        message = "Database populated successfully!"
    except subprocess.CalledProcessError as e:
        message = f"Error populating database: {e}"

    return render(request, 'rag/populate_database.html', {'message': message})