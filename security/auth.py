"""
Firebase Authentication Module for ZATech Bot Admin Dashboard.

This module handles:
- Firebase Admin SDK initialization
- Token verification middleware
- User authorization checks
- Security logging & error handling
"""

import asyncio
import json
import logging
import os
from typing import Optional

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

class FirebaseAuth:
    """Firebase authentication and authorization."""

    _initialized = False 
    

    @classmethod
    def initialize(cls):
        """Initialize Firebase Admin SDK."""

        if cls._initialized:
            logger.info("Firebase Admin SDK already initialized.")
            return

        try:
            creds_json = os.getenv("FIREBASE_CREDENTIALS_JSON")

            if not creds_json:
                raise ValueError("FIREBASE_CREDENTIALS_JSON environment variable is not set.")

            # Load credentials from JSON string
            creds_dict = json.loads(creds_json)
            cred = credentials.Certificate(creds_dict)
            logger.info("Loaded Firebase credentials from FIREBASE_CREDENTIALS_JSON.")

            firebase_admin.initialize_app(cred)
            cls._initialized = True
            logger.info("Firebase Admin SDK initialized successfully.")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in FIREBASE_CREDENTIALS_JSON: {e}")
            raise ValueError("Invalid Firebase credentials format") from e
        
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise

    @staticmethod
    async def verify_token(id_token: str) -> Optional[dict]:
        """Verify Firebase ID token and return Dict with user info."""

        if not id_token or not isinstance(id_token, str):
            logger.warning("Invalid token format received")
            return None
        
        try:
            # Verify token with Firebase (execute blocking call in thread)
            decoded_token = await asyncio.to_thread(auth.verify_id_token, id_token, check_revoked=True)

            # Extract user info
            user_email = decoded_token.get('email', 'unknown')
            user_uid = decoded_token.get('uid', 'unknown')

            logger.info(f"Token verified for user: {user_email} (UID: {user_uid})")
            return decoded_token
        
        # Handle Firebase auth errors
        except auth.ExpiredIdTokenError:
            logger.warning("Token has expired")
            return None
        
        except auth.RevokedIdTokenError:
            logger.warning("Revoked token provided")
            return None
        
        except auth.InvalidIdTokenError as e:
            logger.warning("Invalid token provided")
            return None
        
        except auth.UserDisabledError:
            logger.warning("Token for disabled user provided")
            return None
            
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return None
        
    @staticmethod
    async def check_user_exists(uid: str) -> bool:
        """Check if a user exists in Firebase Auth"""

        if not uid or not isinstance(uid, str):
            logger.warning("Invalid UID format")
            return False
        
        try:
            # Fetch user details without blocking the event loop
            user = await asyncio.to_thread(auth.get_user, uid)
            
            if user.disabled:
                logger.warning(f"User is disabled: {uid}")
                return False
            
            return True
        
        except auth.UserNotFoundError:
            logger.warning(f"User not found: {uid}")
            return False
        
        except Exception as e:
            logger.error(f"Error checking user: {e}")
            return False
        
        
async def get_current_user(request: Request) -> Optional[dict]:
    """Extract and verify user from request"""

    id_token = None

    # Check cookie
    id_token = request.cookies.get("firebase_token")

    if not id_token:
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            id_token = auth_header.split("Bearer ", 1)[1]

    if not id_token:
        return None
    
    # Verify token
    user_info = await FirebaseAuth.verify_token(id_token)

    if not user_info:
        return None
    
    # Verify user exists in Firebase
    user_exits = await FirebaseAuth.check_user_exists(user_info.get("uid"))

    if not user_exits:
        user_email = user_info.get('email', 'unknown')
        logger.warning(f"Valid token but user not registered or disabled: {user_email}")
        return None
    
    return user_info

    
async def require_auth(request: Request) -> dict:
    """FastAPI dependency for routes requiring authentication (AI was used to help write this function)."""

    user = await get_current_user(request)

    if not user:
        # Determine if browser or API request
        accept_header = request.headers.get("accept", "")
        is_browser_request = "text/html" in accept_header

        if is_browser_request:
            # Browser: redirect to login
            raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": "/admin/login"})
        else:
            # API: raise 401
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})

    return user
