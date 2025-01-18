from django.conf import settings

class MediaCorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Add CORS headers for all responses
        response["Access-Control-Allow-Origin"] = ", ".join(settings.CORS_ALLOWED_ORIGINS)
        response["Access-Control-Allow-Credentials"] = "true"
        
        # For media files, add additional headers needed by PDF.js
        if request.path.startswith('/media/'):
            response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            response["Access-Control-Allow-Headers"] = "range"
            response["Access-Control-Expose-Headers"] = "content-length, content-range, accept-ranges"
        # For API endpoints, add headers needed for authentication
        else:
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response["Access-Control-Allow-Headers"] = "accept, accept-encoding, authorization, content-type, dnt, origin, user-agent, x-csrftoken, x-requested-with"
        
        return response 