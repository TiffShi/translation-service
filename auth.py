import os
import httpx
from fastapi import Request, HTTPException, status

#set this as an environment variable in Docker container
#url of the central authentication service from healthcare-app project
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL")

#hardcoded secret for service-to-service communication
SERVICE_TOKEN_SECRET = "db-service-secret-token"

#FastAPI dependency that replicates the authentication logic from the
#healthcare-app's Django JWTAuthenticationMiddleware
#(request: Request) - how FastAPI injects dependencies, its saying:
#"before you run the endpoint code, run this function and pass it to current request object"
async def verify_token(request: Request):
    #check for the service-to-service token
    #service-to-service token is a "pre-shared password" that one
    #microservice uses to prove its identity to another
    service_token = request.headers.get('X-Service-Token')
    if service_token:
        if service_token == SERVICE_TOKEN_SECRET:
            #this is a trusted internal_service
            return {"user_id": "internal_service", "user_type": "service"}

        #service token was provided, but it was incorrect
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token",
        )

    #if no service token, check for a user's JWT Bearer token
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Expected 'Bearer <token>'",
        )

    #the header should be in the format "Bearer <token>"
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Expected 'Bearer <token>'",
        )

    token = parts[1]

    if not AUTH_SERVICE_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured on this server."
        )

    #call the central auth service to verify the token
    verify_url = f"{AUTH_SERVICE_URL}/api/auth/verify/"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        #creates HTTP client session 
        async with httpx.AsyncClient() as client:
            response = await client.get(verify_url, headers=headers, timeout=5.0)
        
        #check if the auth service successfully processed our request
        if response.status_code == 200:
            data = response.json()
            #check if token is good
            if data.get('valid'):
                user_data = data.get('user', {})
                return user_data
            
            #token was invalid
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        # auth service returned an error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: Could not be verified by auth service.",
        )

    except httpx.RequestError as e:
        #auth service is down or there was a network error
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Authentication service unavailable: {e}",
        )
