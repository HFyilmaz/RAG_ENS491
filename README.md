# Retrieval Augmented Generation (RAG) - UN Regulations 

> **Note:** If you're using Docker, skip the manual installation steps and go directly to the [DOCKER Guide](#docker-guide) section. The following manual setup is only needed for local development without Docker.

## Sections
- [Local Development](#local-development)
- [DOCKER Guide](#docker-guide)
- [Password Reset Configuration](#password-reset-configuration)
- [Database Migrations](#database-migrations)
- [Ollama Model Setup](#ollama-model-setup)

## Local Development

Run the following command to install dependencies:
```bash
pip install -r requirements.txt
```

## Elasticsearch Setup

* <b>If docker is not an option, follow the following steps to install Elasticsearch locally:</b>
### Installation
1. Download Elasticsearch 8.11.1:
```
https://www.elastic.co/downloads/past-releases/elasticsearch-8-11-1
```

2. Extract the archive

3. Configure Elasticsearch:
Create/modify `elasticsearch-8.11.1/config/elasticsearch.yml` with the following settings:
```yaml
# Disable security features for development
xpack.security.enabled: false

# Network settings
network.host: 0.0.0.0
http.port: 9200

# Discovery settings
discovery.type: single-node

# CORS settings
http.cors.enabled: true
http.cors.allow-origin: "*"
http.cors.allow-methods: OPTIONS, HEAD, GET, POST, PUT, DELETE
http.cors.allow-headers: X-Requested-With,X-Auth-Token,Content-Type,Content-Length,Authorization

# Disable SSL/TLS for development
xpack.security.http.ssl.enabled: false
xpack.security.transport.ssl.enabled: false
```

4. Start Elasticsearch:
```bash
cd elasticsearch-8.11.1/bin && ./elasticsearch
```

5. Verify the installation:
```bash
curl http://localhost:9200
```
You should see a JSON response with Elasticsearch version information.

### Python Dependencies
The following packages have been added to requirements.txt:
- elasticsearch==8.11.1
- elasticsearch-dsl==8.15.4
- django-elasticsearch-dsl==8.0

Install them using:
```bash
pip install -r requirements.txt
```

### Usage
1. Start Elasticsearch before running the Django server
2. Upload PDF files through the application interface
3. Files will be automatically indexed in Elasticsearch
4. Use the search functionality to find content within PDFs

<br>

## DOCKER Guide

### Prerequisites
1. Navigate to the directory containing `docker-compose.yml`
2. Ensure the `context` fields in `docker-compose.yml` point to the correct source folders for both projects

### Installation and Running
1. Build the Docker containers:
```bash
docker compose build
```

2. Start the containers:
```bash
docker compose up
```

Note: For a fresh start without cache, use:
```bash
docker compose build --no-cache
```

### Ollama Model Setup
1. Pull required models when containers are running:
```bash
docker exec -it ollama ollama pull llama3.1
docker exec -it ollama ollama pull nomic-embed-text
```

2. View pulled models:
```bash
docker exec -it ollama ollama list
```

## Password Reset Configuration

### Setup Requirements
1. Install new dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables in `.env` file:
- `EMAIL_ADDR`: Your Gmail address
- `EMAIL_APP_PASSW`: Your Gmail app password

Note: 
1. Search online for instructions on obtaining a Gmail app password.
2. Locate the `.env` file in the same directory with `docker-compose.yml` file.
### Additional Information
- Reset link validity: 24 hours by default
- Can be modified using `DJANGO_REST_MULTITOKENAUTH_RESET_TOKEN_EXPIRY_TIME` variable

## Database Migrations

### Creating and Applying Migrations
When you make changes to Django models, you need to create and apply migrations. Here's how to do it with Docker:

1. Create new migrations:

```bash
docker exec -it django_app python manage.py makemigrations
```

2. To apply all pending migrations for all apps:
```bash
docker exec -it django_app python manage.py migrate
```

>**Note:** Always make sure your Docker containers are running before executing migration commands.

### To run ollama in a container change the following sections:
<b>In docker-compose.yml remove</b>
```
    extra_hosts:
      - "host.docker.internal:host-gateway"  
```

<b>In llm_model.py and vectordb.py change the following section:</b>

```
# Previous Version for local development
embeddings = OllamaEmbeddings(model="nomic-embed-text",base_url="http://host.docker.internal:11434")

# New Version for container
embeddings = OllamaEmbeddings(model="nomic-embed-text",base_url="http://ollama:11434")
```


