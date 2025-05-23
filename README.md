# RAG_ENS491

### Run the following command to install dependencies:
#### pip install -r requirements.txt

# This branch uses embeddings and LLM model locally

# Current API's
### /chatbot/register
#### Expects JSON Data with "username", "email", and "password"
#### Returns user-related data

### /chatbot/login
#### Expects JSON Data with "username" and "password"
#### Returns user-related data, refresh token and access token

### /chatbot/query
#### Requires Authentication
#### Expects JSON Data with "query"
#### Returns the model response

### /chatbot/get_queries
#### Requires Authentication
#### Returns the list of all queries performed by the authenticated requesting user

### /chatbot/upload_file
#### Requires Authentication
#### Expects form-data with "file" field

### /chatbot/search
#### Expects JSON Data with "search"
#### Returns the list of all files that contain the search query

## Elasticsearch Setup

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

