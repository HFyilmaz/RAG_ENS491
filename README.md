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


