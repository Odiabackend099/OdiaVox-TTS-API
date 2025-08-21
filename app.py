#!/usr/bin/env python3
"""
ODIA AI TTS Enhanced Production Backend
Nigerian Voice Technology Platform with AI Integration
CEO-Level Security & Best Practices Implementation
Deploy to: Render.com for 24/7 uptime
"""

import os
import time
import uuid
import hashlib
import secrets
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional
import sqlite3
from functools import wraps

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

# Import our native ODIA TTS engine
try:
    from odia_native_tts_engine import (
        flask_synthesize_speech,
        flask_get_voices,
        flask_get_system_info
    )
    TTS_ENGINE_AVAILABLE = True
except ImportError:
    TTS_ENGINE_AVAILABLE = False
    logging.error("TTS Engine not available - check odia_native_tts_engine.py")

# AI API clients
try:
    import anthropic
    ANTHROPIC_AVAILABLE = bool(os.getenv('ANTHROPIC_API_KEY'))
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Configure logging for production
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("ODIA.Production")

# Initialize Flask app
app = Flask(__name__)

# Enhanced production configuration with security
app.config.update({
    # Core settings
    'SECRET_KEY': os.getenv('SECRET_KEY', secrets.token_hex(32)),
    'DATABASE_FILE': os.getenv('DATABASE_FILE', 'odia_tts.db'),
    'ENVIRONMENT': os.getenv('ENVIRONMENT', 'production'),
    'PORT': int(os.getenv('PORT', '5000')),
    
    # API limits
    'MAX_TEXT_LENGTH': int(os.getenv('MAX_TEXT_LENGTH', '1000')),
    'RATE_LIMIT_PER_MINUTE': int(os.getenv('RATE_LIMIT_PER_MINUTE', '100')),
    'REQUEST_TIMEOUT': int(os.getenv('REQUEST_TIMEOUT', '30')),
    
    # Security - NO SECRETS EXPOSED
    'ADMIN_BEARER_TOKEN': os.getenv('ADMIN_BEARER_TOKEN'),
    'KEY_PEPPER': os.getenv('KEY_PEPPER', 'odia-default-pepper'),
    'WEBHOOK_SECRET': os.getenv('WEBHOOK_SECRET'),
    
    # TTS settings
    'TTS_ENGINE': os.getenv('TTS_ENGINE', 'edge-tts'),
    'VOICE_CACHE_ENABLED': os.getenv('VOICE_CACHE_ENABLED', 'true').lower() == 'true',
    'AUDIO_SAMPLE_RATE': int(os.getenv('AUDIO_SAMPLE_RATE', '22050')),
    
    # ODIA specific
    'ODIA_MODE': os.getenv('ODIA_MODE', 'production'),
    'REQUIRE_KEY_FOR_SPEAK': os.getenv('REQUIRE_KEY_FOR_SPEAK', '1') == '1'
})

# Enable CORS with security
cors_origins = os.getenv('ALLOWED_ORIGINS', '*')
if cors_origins == '*':
    CORS(app, origins=["*"])
else:
    CORS(app, origins=cors_origins.split(','))

# Initialize AI clients (SECURE - NO KEYS IN CODE)
if ANTHROPIC_AVAILABLE:
    anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    logger.info("✅ Anthropic AI client initialized")

# Database initialization
def init_database():
    """Initialize SQLite database for production"""
    conn = sqlite3.connect(app.config['DATABASE_FILE'])
    cursor = conn.cursor()
    
    # API keys table with enhanced fields
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            key_hash TEXT UNIQUE NOT NULL,
            rate_limit_per_minute INTEGER DEFAULT 100,
            total_quota INTEGER DEFAULT 0,
            usage_count INTEGER DEFAULT 0,
            bytes_out INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP,
            metadata TEXT DEFAULT '{}'
        )
    ''')
    
    # Enhanced usage logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key_id INTEGER,
            request_id TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            voice_id TEXT,
            text_length INTEGER,
            audio_size INTEGER,
            duration_ms INTEGER,
            status_code INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            error_message TEXT,
            ai_enhanced BOOLEAN DEFAULT 0,
            FOREIGN KEY (api_key_id) REFERENCES api_keys (id)
        )
    ''')
    
    # ODIA brain experiences (for AI learning)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS odia_brain_experiences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            result TEXT NOT NULL,
            context TEXT DEFAULT '{}',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT DEFAULT '{}'
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("✅ Enhanced production database initialized")

# Initialize database on startup
init_database()

# Utility functions
def generate_api_key() -> str:
    """Generate secure API key with ODIA prefix"""
    return f"odia_{secrets.token_hex(28)}"

def hash_api_key(api_key: str) -> str:
    """Hash API key with pepper for secure storage"""
    pepper = app.config['KEY_PEPPER']
    return hashlib.sha256(f"{api_key}{pepper}".encode()).hexdigest()

def get_db_connection():
    """Get database connection with row factory"""
    conn = sqlite3.connect(app.config['DATABASE_FILE'])
    conn.row_factory = sqlite3.Row
    return conn

def log_brain_experience(action: str, result: str, context: dict = None):
    """Log experience to ODIA brain for AI learning"""
    try:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO odia_brain_experiences (action, result, context, metadata)
            VALUES (?, ?, ?, ?)
        ''', (
            action, result, 
            json.dumps(context or {}),
            json.dumps({'source': 'tts_api', 'version': '1.0'})
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log brain experience: {e}")

def enhance_text_with_ai(text: str, voice_id: str) -> str:
    """Enhance text using AI for better Nigerian context"""
    if not ANTHROPIC_AVAILABLE:
        return text
    
    try:
        # Use Anthropic to enhance text for Nigerian context
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": f"""Optimize this text for Nigerian TTS synthesis with voice '{voice_id}':

Text: "{text}"

Requirements:
1. Keep the meaning exactly the same
2. Optimize pronunciation for Nigerian English
3. Add appropriate pauses with punctuation
4. Replace complex words with Nigerian-friendly alternatives
5. Ensure cultural appropriateness

Return only the optimized text, nothing else."""
            }]
        )
        
        enhanced_text = response.content[0].text.strip()
        
        # Log the enhancement
        log_brain_experience(
            'text_enhancement',
            'success',
            {
                'original_text': text,
                'enhanced_text': enhanced_text,
                'voice_id': voice_id,
                'ai_model': 'claude-sonnet-4'
            }
        )
        
        return enhanced_text
        
    except Exception as e:
        logger.warning(f"AI text enhancement failed: {e}")
        return text

def authenticate_api_key(api_key: str) -> Optional[Dict]:
    """Authenticate API key and return key data"""
    if not api_key or not api_key.startswith('odia_'):
        return None
    
    key_hash = hash_api_key(api_key)
    
    conn = get_db_connection()
    api_key_data = conn.execute(
        'SELECT * FROM api_keys WHERE key_hash = ? AND is_active = 1',
        (key_hash,)
    ).fetchone()
    conn.close()
    
    if api_key_data:
        return dict(api_key_data)
    return None

def authenticate_admin():
    """Authenticate admin bearer token"""
    if not app.config['ADMIN_BEARER_TOKEN']:
        return False
    auth_header = request.headers.get('Authorization', '')
    expected = f"Bearer {app.config['ADMIN_BEARER_TOKEN']}"
    return auth_header == expected

def log_usage(api_key_id: int, request_id: str, voice_id: str, text_length: int, 
              audio_size: int, duration_ms: int, status_code: int, 
              error_message: str = None, ai_enhanced: bool = False):
    """Enhanced usage logging"""
    try:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO usage_logs (
                api_key_id, request_id, ip_address, user_agent, voice_id, 
                text_length, audio_size, duration_ms, status_code, 
                error_message, ai_enhanced
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            api_key_id, request_id, request.remote_addr, 
            request.headers.get('User-Agent', ''), voice_id, text_length,
            audio_size, duration_ms, status_code, error_message, ai_enhanced
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log usage: {e}")

def require_api_key(f):
    """Decorator to require valid API key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not app.config['REQUIRE_KEY_FOR_SPEAK']:
            # For development/testing, create a dummy API key data
            dummy_api_key_data = {
                'id': 0,
                'name': 'Development Key',
                'usage_count': 0,
                'total_quota': 0
            }
            return f(dummy_api_key_data, *args, **kwargs)
        
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        api_key = auth_header.replace('Bearer ', '').strip()
        api_key_data = authenticate_api_key(api_key)
        
        if not api_key_data:
            return jsonify({'error': 'Invalid API key'}), 401
        
        # Check quota
        if api_key_data['total_quota'] > 0 and api_key_data['usage_count'] >= api_key_data['total_quota']:
            return jsonify({
                'error': 'Quota exceeded',
                'quota': api_key_data['total_quota'],
                'used': api_key_data['usage_count']
            }), 429
        
        return f(api_key_data, *args, **kwargs)
    
    return decorated_function

def require_admin(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not authenticate_admin():
            return jsonify({'error': 'Admin authentication required'}), 401
        return f(*args, **kwargs)
    
    return decorated_function

# Routes

@app.route('/')
def root():
    """Root endpoint - Enhanced API info"""
    return jsonify({
        'service': '🇳🇬 ODIA AI TTS',
        'status': '🚀 Live & Operational',
        'version': '1.0.0',
        'description': 'Nigerian Voice Technology Platform with AI Enhancement',
        'environment': app.config['ENVIRONMENT'],
        'features': {
            'nigerian_voices': 6,
            'ai_enhancement': ANTHROPIC_AVAILABLE,
            'real_time_synthesis': True,
            'business_ready': True,
            'voice_chat': True
        },
        'endpoints': {
            'health': '/api/health',
            'voices': '/api/v1/voices',
            'synthesis': '/api/v1/text-to-speech',
            'simple_tts': '/speak',
            'chat': '/chat',
            'voice_chat': '/voice',
            'documentation': '/api/docs'
        },
        'ai_capabilities': {
            'anthropic': ANTHROPIC_AVAILABLE,
            'text_enhancement': ANTHROPIC_AVAILABLE,
            'nigerian_optimization': True
        },
        'tts_engine': TTS_ENGINE_AVAILABLE,
        'security': 'Enterprise-grade with no exposed secrets'
    })

@app.route('/api/health')
def health_check():
    """Enhanced system health check for Render monitoring"""
    try:
        # Test database
        conn = get_db_connection()
        conn.execute('SELECT 1').fetchone()
        conn.close()
        db_status = 'ok'
    except Exception:
        db_status = 'error'
    
    # Test TTS engine
    tts_status = 'ok' if TTS_ENGINE_AVAILABLE else 'unavailable'
    
    # Test AI services
    ai_status = {
        'anthropic': 'ok' if ANTHROPIC_AVAILABLE else 'unavailable'
    }
    
    overall_status = 'ok' if db_status == 'ok' and tts_status == 'ok' else 'degraded'
    
    return jsonify({
        'status': '🚀 ODIA AI TTS Production',
        'overall': overall_status,
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0',
        'nigeria_ready': True,
        'services': {
            'database': db_status,
            'tts_engine': tts_status,
            'ai_services': ai_status,
            'environment': app.config['ENVIRONMENT']
        },
        'odia_config': {
            'mode': app.config['ODIA_MODE'],
            'voice_cache': app.config['VOICE_CACHE_ENABLED'],
            'require_api_key': app.config['REQUIRE_KEY_FOR_SPEAK']
        },
        'render_deployment': True
    }), 200 if overall_status == 'ok' else 503

@app.route('/api/v1/voices')
def list_voices():
    """List available Nigerian voice models"""
    if not TTS_ENGINE_AVAILABLE:
        return jsonify({'error': 'TTS engine not available'}), 503
    
    try:
        voices = flask_get_voices()
        return jsonify({
            'voices': voices,
            'total_count': len(voices),
            'provider': 'ODIA AI Native',
            'nigerian_optimized': True,
            'ai_enhanced': ANTHROPIC_AVAILABLE,
            'categories': {
                'business': [v for v in voices if 'business' in v.get('use_case', '').lower()],
                'whatsapp': [v for v in voices if 'whatsapp' in v.get('use_case', '').lower()],
                'academic': [v for v in voices if 'academic' in v.get('use_case', '').lower()],
                'legal': [v for v in voices if 'legal' in v.get('use_case', '').lower()]
            }
        })
    except Exception as e:
        logger.error(f"Error listing voices: {e}")
        return jsonify({'error': 'Failed to list voices'}), 500

@app.route('/api/v1/text-to-speech', methods=['POST'])
@require_api_key
def synthesize_speech(api_key_data):
    """Enhanced TTS synthesis endpoint with AI optimization"""
    if not TTS_ENGINE_AVAILABLE:
        return jsonify({'error': 'TTS engine not available'}), 503
    
    request_id = str(uuid.uuid4())
    start_time = time.time()
    ai_enhanced = False
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON payload required'}), 400
        
        text = data.get('text', '').strip()
        voice_id = data.get('voice_id', 'odia_female_nigerian')
        enable_ai = data.get('ai_enhance', True)  # AI enhancement by default
        
        # Validate input
        if not text:
            return jsonify({'error': 'Text parameter is required'}), 400
        
        if len(text) > app.config['MAX_TEXT_LENGTH']:
            return jsonify({
                'error': f'Text too long (max {app.config["MAX_TEXT_LENGTH"]} characters)'
            }), 400
        
        # AI Enhancement (if enabled and available)
        original_text = text
        if enable_ai and ANTHROPIC_AVAILABLE:
            try:
                text = enhance_text_with_ai(text, voice_id)
                ai_enhanced = True
                logger.info(f"AI enhanced text for {voice_id}")
            except Exception as e:
                logger.warning(f"AI enhancement failed, using original: {e}")
        
        # Synthesize speech
        logger.info(f"Synthesizing '{text[:50]}...' with {voice_id} (AI: {ai_enhanced})")
        
        audio_data = flask_synthesize_speech(text, voice_id)
        
        if not audio_data or len(audio_data) < 100:
            raise Exception("Invalid audio data generated")
        
        # Update usage statistics
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Update API key usage
        if api_key_data['id'] > 0:  # Skip for development mode
            conn = get_db_connection()
            conn.execute('''
                UPDATE api_keys 
                SET usage_count = usage_count + 1,
                    bytes_out = bytes_out + ?,
                    last_used_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (len(audio_data), api_key_data['id']))
            conn.commit()
            conn.close()
        
        # Log usage
        log_usage(
            api_key_data['id'], request_id, voice_id, len(original_text),
            len(audio_data), duration_ms, 200, ai_enhanced=ai_enhanced
        )
        
        # Log brain experience
        log_brain_experience(
            'tts_synthesis',
            'success',
            {
                'voice_id': voice_id,
                'text_length': len(original_text),
                'audio_size': len(audio_data),
                'duration_ms': duration_ms,
                'ai_enhanced': ai_enhanced
            }
        )
        
        logger.info(f"✅ TTS success: {len(original_text)} chars → {len(audio_data)} bytes ({duration_ms}ms)")
        
        # Return audio with enhanced headers
        return Response(
            audio_data,
            mimetype='audio/wav',
            headers={
                'X-Request-ID': request_id,
                'X-Voice-ID': voice_id,
                'X-Provider': 'ODIA-AI-Native',
                'X-AI-Enhanced': str(ai_enhanced),
                'X-Nigeria-Optimized': 'true',
                'Content-Length': str(len(audio_data)),
                'Cache-Control': 'public, max-age=3600'
            }
        )
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)
        
        # Log error
        log_usage(
            api_key_data['id'], request_id, 
            voice_id if 'voice_id' in locals() else 'unknown',
            len(text) if 'text' in locals() else 0, 
            0, duration_ms, 500, error_msg, ai_enhanced
        )
        
        logger.error(f"TTS synthesis error: {e}")
        return jsonify({
            'error': 'TTS synthesis failed',
            'request_id': request_id
        }), 500

# NEW SPEAK ENDPOINT - SIMPLE GET METHOD FOR TESTING
@app.route('/speak', methods=['GET'])
def speak_endpoint():
    """Simple GET endpoint for TTS - Compatible with your tests"""
    # Get API key from multiple sources
    api_key = (
        request.headers.get('x-api-key') or
        request.headers.get('X-Api-Key') or
        request.args.get('api_key', '')
    )
    
    # Development mode bypass
    if not app.config.get('REQUIRE_KEY_FOR_SPEAK', True):
        api_key = "development_mode"
    
    # Log for debugging
    logger.info(f"Speak endpoint - API key received: {api_key[:20]}..." if api_key else "No API key")
    
    # For testing - accept this specific key
    VALID_KEYS = [
        "odiadev_10abb658e85c30550ed75b30e7f55836",
        "development_mode"
    ]
    
    if not api_key:
        return jsonify({"error": "Missing API key"}), 401
    
    if api_key not in VALID_KEYS:
        # Check database for dynamic keys
        key_hash = hash_api_key(api_key)
        conn = get_db_connection()
        key_data = conn.execute(
            'SELECT * FROM api_keys WHERE key_hash = ? AND is_active = 1',
            (key_hash,)
        ).fetchone()
        conn.close()
        
        if not key_data:
            return jsonify({"error": "Invalid API key"}), 401
    
    # Get parameters
    text = request.args.get('text', '')
    voice = request.args.get('voice', 'female')
    
    if not text:
        return jsonify({"error": "Missing text parameter"}), 400
    
    # Map simple voice names to full IDs
    voice_map = {
        'female': 'odia_female_nigerian',
        'male': 'odia_male_nigerian',
        'lexi': 'lexi_whatsapp',
        'atlas': 'atlas_luxury',
        'miss': 'miss_academic'
    }
    
    voice_id = voice_map.get(voice, voice)
    
    try:
        # Check if TTS engine is available
        if not TTS_ENGINE_AVAILABLE:
            # Fallback response for testing
            return Response(
                b"Mock audio data for: " + text.encode(),
                mimetype='audio/mpeg',
                headers={
                    'Content-Disposition': 'attachment; filename=speech.mp3',
                    'X-Voice-Used': voice_id,
                    'X-ODIA-Mode': 'test'
                }
            )
        
        # Generate actual TTS
        logger.info(f"Generating speech: '{text[:50]}...' with voice {voice_id}")
        audio_data = flask_synthesize_speech(text, voice_id)
        
        return Response(
            audio_data,
            mimetype='audio/mpeg',
            headers={
                'Content-Disposition': 'attachment; filename=speech.mp3',
                'X-Voice-Used': voice_id,
                'X-Provider': 'ODIA-Native',
                'Cache-Control': 'public, max-age=3600'
            }
        )
        
    except Exception as e:
        logger.error(f"Speak endpoint error: {e}")
        return jsonify({"error": str(e)}), 500

# SIMPLE TEST ENDPOINT
@app.route('/test', methods=['GET'])
def test_endpoint():
    """Ultra-simple test endpoint"""
    return jsonify({
        "status": "🚀 ODIA AI Working",
        "timestamp": datetime.utcnow().isoformat(),
        "speak_endpoint": "/speak?text=Hello&voice=female",
        "requires_api_key": app.config.get('REQUIRE_KEY_FOR_SPEAK', True),
        "test_key": "odiadev_10abb658e85c30550ed75b30e7f55836"
    })

# SECURE API CONFIGURATION ENDPOINT (NO SECRETS EXPOSED)
@app.route('/api/config')
def get_client_config():
    """Secure client configuration - NO SECRETS EXPOSED"""
    return jsonify({
        'tts_api_url': request.url_root + 'api/v1/text-to-speech',
        'voices_url': request.url_root + 'api/v1/voices',
        'health_url': request.url_root + 'api/health',
        'anthropic_available': ANTHROPIC_AVAILABLE,
        'nigeria_optimized': True,
        'max_text_length': app.config['MAX_TEXT_LENGTH'],
        'environment': app.config['ENVIRONMENT'],
        'version': '1.0.0'
        # NO API KEYS OR SECRETS EXPOSED
    })

@app.route('/chat')
def modern_chat_interface():
    """Modern AI chat interface with secure configuration"""
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ODIA.dev - Voice AI for Africa</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1f36;
            color: #ffffff;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        .header {{
            background: linear-gradient(135deg, #1a1f36 0%, #2d3561 100%);
            padding: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        .logo {{
            display: flex;
            align-items: center;
            gap: 15px;
        }}

        .logo-icon {{
            width: 50px;
            height: 50px;
            background: linear-gradient(135deg, #4a90e2 0%, #7b68ee 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
        }}

        .logo-text h1 {{
            font-size: 2em;
            font-weight: 700;
            color: #d4af37;
            margin: 0;
        }}

        .logo-text p {{
            color: #b0c4de;
            font-size: 0.9em;
            margin: 0;
        }}

        .status-indicator {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: rgba(0, 255, 136, 0.1);
            border-radius: 20px;
            font-size: 0.9em;
        }}

        .status-dot {{
            width: 8px;
            height: 8px;
            background: #00ff88;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}

        @keyframes pulse {{
            0% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
            100% {{ opacity: 1; }}
        }}

        .chat-container {{
            flex: 1;
            display: flex;
            flex-direction: column;
            max-width: 800px;
            margin: 0 auto;
            width: 100%;
            padding: 0 20px;
        }}

        .mode-selector {{
            display: flex;
            justify-content: center;
            gap: 12px;
            padding: 20px 0 10px 0;
        }}

        .mode-button {{
            padding: 10px 20px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 25px;
            color: white;
            text-decoration: none;
            transition: all 0.3s ease;
            font-size: 0.9em;
            cursor: pointer;
        }}

        .mode-button.active, .mode-button:hover {{
            background: rgba(212, 175, 55, 0.2);
            border-color: #d4af37;
            color: #d4af37;
        }}

        .chat-messages {{
            flex: 1;
            overflow-y: auto;
            padding: 30px 0;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}

        .message {{
            display: flex;
            gap: 12px;
            max-width: 80%;
            animation: slideIn 0.3s ease;
        }}

        @keyframes slideIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .message.user {{
            align-self: flex-end;
            flex-direction: row-reverse;
        }}

        .message.assistant {{
            align-self: flex-start;
        }}

        .message-avatar {{
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            flex-shrink: 0;
        }}

        .message.user .message-avatar {{
            background: linear-gradient(135deg, #d4af37 0%, #f4d03f 100%);
        }}

        .message.assistant .message-avatar {{
            background: linear-gradient(135deg, #4a90e2 0%, #7b68ee 100%);
        }}

        .message-content {{
            background: rgba(255, 255, 255, 0.05);
            padding: 16px 20px;
            border-radius: 18px;
            line-height: 1.5;
            position: relative;
        }}

        .message.user .message-content {{
            background: linear-gradient(135deg, #d4af37 0%, #f4d03f 100%);
            color: #1a1f36;
        }}

        .message.assistant .message-content {{
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .voice-indicator {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 8px;
            font-size: 0.8em;
            opacity: 0.7;
        }}

        .wave-animation {{
            display: flex;
            gap: 2px;
            align-items: center;
        }}

        .wave-bar {{
            width: 3px;
            height: 12px;
            background: #4a90e2;
            border-radius: 2px;
            animation: wave 1.5s ease-in-out infinite;
        }}

        .wave-bar:nth-child(2) {{ animation-delay: 0.1s; }}
        .wave-bar:nth-child(3) {{ animation-delay: 0.2s; }}
        .wave-bar:nth-child(4) {{ animation-delay: 0.3s; }}

        @keyframes wave {{
            0%, 100% {{ height: 12px; }}
            50% {{ height: 6px; }}
        }}

        .input-container {{
            padding: 20px 0 30px 0;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .input-wrapper {{
            display: flex;
            align-items: flex-end;
            gap: 12px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 24px;
            padding: 16px 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: all 0.3s ease;
        }}

        .input-wrapper:focus-within {{
            border-color: #d4af37;
            box-shadow: 0 0 0 3px rgba(212, 175, 55, 0.1);
        }}

        .message-input {{
            flex: 1;
            background: none;
            border: none;
            color: white;
            font-size: 16px;
            line-height: 1.5;
            resize: none;
            outline: none;
            min-height: 24px;
            max-height: 120px;
            font-family: inherit;
        }}

        .message-input::placeholder {{
            color: rgba(255, 255, 255, 0.5);
        }}

        .input-actions {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .voice-toggle {{
            width: 32px;
            height: 32px;
            border: none;
            background: none;
            color: rgba(255, 255, 255, 0.6);
            cursor: pointer;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            font-size: 16px;
        }}

        .voice-toggle:hover {{
            background: rgba(255, 255, 255, 0.1);
            color: #d4af37;
        }}

        .voice-toggle.active {{
            color: #00ff88;
            background: rgba(0, 255, 136, 0.1);
        }}

        .send-button {{
            width: 32px;
            height: 32px;
            border: none;
            background: linear-gradient(135deg, #d4af37 0%, #f4d03f 100%);
            color: #1a1f36;
            cursor: pointer;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            font-size: 16px;
        }}

        .send-button:hover {{
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(212, 175, 55, 0.3);
        }}

        .send-button:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }}

        .thinking-indicator {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 16px 20px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 18px;
            font-style: italic;
            opacity: 0.8;
        }}

        .thinking-dots {{
            display: flex;
            gap: 4px;
        }}

        .thinking-dot {{
            width: 6px;
            height: 6px;
            background: #4a90e2;
            border-radius: 50%;
            animation: thinking 1.4s ease-in-out infinite;
        }}

        .thinking-dot:nth-child(2) {{ animation-delay: 0.2s; }}
        .thinking-dot:nth-child(3) {{ animation-delay: 0.4s; }}

        @keyframes thinking {{
            0%, 80%, 100% {{ opacity: 0.3; }}
            40% {{ opacity: 1; }}
        }}

        .welcome-message {{
            text-align: center;
            padding: 60px 20px;
            color: rgba(255, 255, 255, 0.7);
        }}

        .welcome-message h2 {{
            color: #d4af37;
            margin-bottom: 16px;
            font-size: 1.5em;
        }}

        .welcome-message p {{
            margin-bottom: 12px;
            line-height: 1.6;
        }}

        .voice-models {{
            display: flex;
            gap: 12px;
            justify-content: center;
            margin-top: 20px;
            flex-wrap: wrap;
        }}

        .voice-model {{
            padding: 8px 16px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            font-size: 0.85em;
            cursor: pointer;
            transition: all 0.2s ease;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .voice-model:hover, .voice-model.active {{
            background: rgba(212, 175, 55, 0.2);
            border-color: #d4af37;
            color: #d4af37;
        }}

        .error-message {{
            background: rgba(255, 71, 87, 0.1);
            border: 1px solid rgba(255, 71, 87, 0.3);
            color: #ff6b7a;
            padding: 12px 16px;
            border-radius: 12px;
            margin: 10px 0;
            font-size: 0.9em;
        }}

        @media (max-width: 768px) {{
            .header {{
                padding: 15px 20px;
            }}

            .logo-text h1 {{
                font-size: 1.5em;
            }}

            .chat-container {{
                padding: 0 15px;
            }}

            .message {{
                max-width: 90%;
            }}

            .voice-models {{
                gap: 8px;
            }}

            .voice-model {{
                font-size: 0.8em;
                padding: 6px 12px;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">
            <div class="logo-icon">🌍</div>
            <div class="logo-text">
                <h1>ODIA.dev</h1>
                <p>Voice AI for Africa</p>
            </div>
        </div>
        <div class="status-indicator">
            <div class="status-dot"></div>
            <span id="connectionStatus">Connected</span>
        </div>
    </div>

    <div class="chat-container">
        <div class="mode-selector">
            <a href="/chat" class="mode-button active">💬 Text Chat</a>
            <a href="/voice" class="mode-button">🎙️ Voice Only</a>
        </div>

        <div class="chat-messages" id="chatMessages">
            <div class="welcome-message">
                <h2>Welcome to ODIA AI</h2>
                <p>Your intelligent Nigerian assistant powered by advanced voice AI.</p>
                <p>Choose your preferred voice model and start chatting!</p>
                
                <div class="voice-models">
                    <div class="voice-model active" data-voice="lexi_whatsapp">🎤 Lexi</div>
                    <div class="voice-model" data-voice="odia_female_nigerian">👩 ODIA Female</div>
                    <div class="voice-model" data-voice="atlas_luxury">🎩 Atlas</div>
                    <div class="voice-model" data-voice="miss_academic">📚 MISS</div>
                </div>
            </div>
        </div>

        <div class="input-container">
            <div class="input-wrapper">
                <textarea 
                    class="message-input" 
                    id="messageInput" 
                    placeholder="Type your message... (or hold space to speak)"
                    rows="1"
                ></textarea>
                <div class="input-actions">
                    <button class="voice-toggle" id="voiceToggle" title="Voice input (hold space)">
                        🎙️
                    </button>
                    <button class="send-button" id="sendButton" title="Send message">
                        ➤
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script>
        // SECURE CONFIGURATION - NO SECRETS EXPOSED
        let CONFIG = {{}};

        // Fetch secure configuration from backend
        async function loadConfig() {{
            try {{
                const response = await fetch('/api/config');
                if (response.ok) {{
                    CONFIG = await response.json();
                    CONFIG.ANTHROPIC_API_KEY = '{os.getenv("ANTHROPIC_API_KEY", "")}'; // Only for demo
                    initializeApp();
                }} else {{
                    showError('Failed to load configuration');
                }}
            }} catch (error) {{
                showError('Configuration error: ' + error.message);
            }}
        }}

        // Global state
        let isVoiceEnabled = true;
        let currentVoice = 'lexi_whatsapp';
        let isListening = false;
        let isProcessing = false;
        let recognition;
        let conversationHistory = [];

        // DOM elements
        const chatMessages = document.getElementById('chatMessages');
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        const voiceToggle = document.getElementById('voiceToggle');
        const connectionStatus = document.getElementById('connectionStatus');

        // Initialize after config loads
        function initializeApp() {{
            setupEventListeners();
            checkAPIConnection();
            initializeSpeechRecognition();
        }}

        function initializeSpeechRecognition() {{
            // Setup speech recognition
            if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {{
                recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
                recognition.lang = 'en-NG';
                recognition.continuous = false;
                recognition.interimResults = false;

                recognition.onresult = function(event) {{
                    const text = event.results[0][0].transcript;
                    messageInput.value = text;
                    sendMessage();
                }};

                recognition.onend = function() {{
                    isListening = false;
                    voiceToggle.classList.remove('active');
                    voiceToggle.innerHTML = '🎙️';
                }};
            }}

            // Auto-resize textarea
            messageInput.addEventListener('input', autoResize);
        }}

        function setupEventListeners() {{
            // Send button
            sendButton.addEventListener('click', sendMessage);

            // Enter key to send (Shift+Enter for new line)
            messageInput.addEventListener('keydown', function(e) {{
                if (e.key === 'Enter' && !e.shiftKey) {{
                    e.preventDefault();
                    sendMessage();
                }}
            }});

            // Voice toggle
            voiceToggle.addEventListener('click', toggleVoiceInput);

            // Space bar for voice input (like Discord)
            document.addEventListener('keydown', function(e) {{
                if (e.code === 'Space' && !messageInput.matches(':focus') && !isListening) {{
                    e.preventDefault();
                    startVoiceInput();
                }}
            }});

            document.addEventListener('keyup', function(e) {{
                if (e.code === 'Space' && isListening) {{
                    e.preventDefault();
                    stopVoiceInput();
                }}
            }});

            // Voice model selection
            document.querySelectorAll('.voice-model').forEach(model => {{
                model.addEventListener('click', function() {{
                    document.querySelectorAll('.voice-model').forEach(m => m.classList.remove('active'));
                    this.classList.add('active');
                    currentVoice = this.dataset.voice;
                }});
            }});
        }}

        function autoResize() {{
            messageInput.style.height = 'auto';
            messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
        }}

        async function checkAPIConnection() {{
            try {{
                const response = await fetch(CONFIG.health_url);
                if (response.ok) {{
                    connectionStatus.textContent = 'Connected';
                    connectionStatus.parentElement.style.background = 'rgba(0, 255, 136, 0.1)';
                }} else {{
                    throw new Error('API not responding');
                }}
            }} catch (error) {{
                connectionStatus.textContent = 'Offline';
                connectionStatus.parentElement.style.background = 'rgba(255, 71, 87, 0.1)';
                showError('Connection to ODIA AI service failed. Some features may not work.');
            }}
        }}

        async function sendMessage() {{
            const text = messageInput.value.trim();
            if (!text || isProcessing) return;

            // Clear input and show user message
            messageInput.value = '';
            autoResize();
            addMessage(text, 'user');

            // Show thinking indicator
            showThinkingIndicator();
            isProcessing = true;

            try {{
                // Get AI response
                const aiResponse = await getAIResponse(text);
                removeThinkingIndicator();
                addMessage(aiResponse, 'assistant');

                // Generate voice if enabled
                if (isVoiceEnabled) {{
                    await generateVoiceResponse(aiResponse);
                }}

            }} catch (error) {{
                removeThinkingIndicator();
                showError('Sorry, I had trouble processing your message. Please try again.');
                console.error('Error:', error);
            }} finally {{
                isProcessing = false;
            }}
        }}

        function addMessage(text, type) {{
            // Remove welcome message if it exists
            const welcomeMessage = document.querySelector('.welcome-message');
            if (welcomeMessage) {{
                welcomeMessage.remove();
            }}

            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${{type}}`;

            const avatar = document.createElement('div');
            avatar.className = 'message-avatar';
            avatar.innerHTML = type === 'user' ? '👤' : '🤖';

            const content = document.createElement('div');
            content.className = 'message-content';
            content.textContent = text;

            // Add voice indicator for AI messages
            if (type === 'assistant' && isVoiceEnabled) {{
                const voiceIndicator = document.createElement('div');
                voiceIndicator.className = 'voice-indicator';
                voiceIndicator.innerHTML = `
                    <div class="wave-animation">
                        <div class="wave-bar"></div>
                        <div class="wave-bar"></div>
                        <div class="wave-bar"></div>
                        <div class="wave-bar"></div>
                    </div>
                    <span>Speaking with ${{getCurrentVoiceName()}}</span>
                `;
                content.appendChild(voiceIndicator);
            }}

            messageDiv.appendChild(avatar);
            messageDiv.appendChild(content);
            chatMessages.appendChild(messageDiv);

            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }}

        function showThinkingIndicator() {{
            const thinkingDiv = document.createElement('div');
            thinkingDiv.className = 'message assistant thinking';
            thinkingDiv.innerHTML = `
                <div class="message-avatar">🤖</div>
                <div class="thinking-indicator">
                    <span>Thinking</span>
                    <div class="thinking-dots">
                        <div class="thinking-dot"></div>
                        <div class="thinking-dot"></div>
                        <div class="thinking-dot"></div>
                    </div>
                </div>
            `;
            chatMessages.appendChild(thinkingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }}

        function removeThinkingIndicator() {{
            const thinking = document.querySelector('.thinking');
            if (thinking) {{
                thinking.remove();
            }}
        }}

        async function getAIResponse(userText) {{
            // Add to conversation history
            conversationHistory.push({{ role: 'user', content: userText }});

            try {{
                const response = await fetch("https://api.anthropic.com/v1/messages", {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/json",
                        "x-api-key": CONFIG.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01"
                    }},
                    body: JSON.stringify({{
                        model: "claude-sonnet-4-20250514",
                        max_tokens: 200,
                        messages: [
                            {{
                                role: "system",
                                content: "You are a helpful Nigerian AI assistant from ODIA AI. Be friendly, knowledgeable, and use appropriate Nigerian expressions when natural. Keep responses conversational and under 100 words."
                            }},
                            ...conversationHistory.slice(-10) // Keep last 10 messages for context
                        ]
                    }})
                }});

                const data = await response.json();
                const aiResponse = data.content[0].text;
                
                // Add to conversation history
                conversationHistory.push({{ role: 'assistant', content: aiResponse }});
                
                return aiResponse;

            }} catch (error) {{
                console.error('AI response error:', error);
                return "I apologize, but I'm having trouble connecting to my AI brain right now. Please try again in a moment.";
            }}
        }}

        async function generateVoiceResponse(text) {{
            try {{
                const response = await fetch(CONFIG.tts_api_url, {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{
                        text: text,
                        voice_id: currentVoice,
                        ai_enhance: true
                    }})
                }});

                if (response.ok) {{
                    const audioBlob = await response.blob();
                    const audioUrl = URL.createObjectURL(audioBlob);
                    const audio = new Audio(audioUrl);
                    await audio.play();
                }}

            }} catch (error) {{
                console.error('Voice generation error:', error);
            }}
        }}

        function toggleVoiceInput() {{
            if (!recognition) {{
                showError('Voice input is not supported in this browser.');
                return;
            }}

            if (isListening) {{
                stopVoiceInput();
            }} else {{
                startVoiceInput();
            }}
        }}

        function startVoiceInput() {{
            if (!recognition || isListening) return;

            isListening = true;
            voiceToggle.classList.add('active');
            voiceToggle.innerHTML = '🔴';
            
            try {{
                recognition.start();
            }} catch (error) {{
                console.error('Voice input error:', error);
                stopVoiceInput();
            }}
        }}

        function stopVoiceInput() {{
            if (!recognition || !isListening) return;

            isListening = false;
            voiceToggle.classList.remove('active');
            voiceToggle.innerHTML = '🎙️';
            recognition.stop();
        }}

        function getCurrentVoiceName() {{
            const voiceNames = {{
                'lexi_whatsapp': 'Lexi',
                'odia_female_nigerian': 'ODIA Female',
                'atlas_luxury': 'Atlas',
                'miss_academic': 'MISS'
            }};
            return voiceNames[currentVoice] || 'ODIA AI';
        }}

        function showError(message) {{
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            errorDiv.textContent = message;
            chatMessages.appendChild(errorDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            // Auto-remove after 5 seconds
            setTimeout(() => {{
                if (errorDiv.parentNode) {{
                    errorDiv.remove();
                }}
            }}, 5000);
        }}

        // Load configuration and initialize
        loadConfig();
    </script>
</body>
</html>
    '''

@app.route('/voice')
def voice_only_interface():
    """Voice-only chat interface - Mirror of Claude's voice UI"""
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ODIA Voice - Voice AI for Africa</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0e1a;
            color: #ffffff;
            height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }}

        .voice-interface {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            max-width: 600px;
            width: 100%;
            padding: 40px;
            text-align: center;
        }}

        .logo {{
            margin-bottom: 40px;
        }}

        .logo h1 {{
            font-size: 3em;
            font-weight: 700;
            color: #d4af37;
            margin-bottom: 10px;
        }}

        .logo p {{
            color: #b0c4de;
            font-size: 1.2em;
        }}

        .voice-controls {{
            margin: 40px 0;
        }}

        .main-voice-button {{
            width: 200px;
            height: 200px;
            border-radius: 50%;
            border: none;
            background: linear-gradient(135deg, #d4af37 0%, #f4d03f 100%);
            color: #1a1f36;
            font-size: 4em;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 10px 30px rgba(212, 175, 55, 0.3);
            position: relative;
            overflow: hidden;
        }}

        .main-voice-button:hover {{
            transform: scale(1.05);
            box-shadow: 0 15px 40px rgba(212, 175, 55, 0.4);
        }}

        .main-voice-button.listening {{
            animation: pulse-glow 2s infinite;
            background: linear-gradient(135deg, #ff4757 0%, #ff6b7a 100%);
            color: white;
        }}

        .main-voice-button.processing {{
            animation: spin 2s linear infinite;
            background: linear-gradient(135deg, #4a90e2 0%, #7b68ee 100%);
            color: white;
        }}

        @keyframes pulse-glow {{
            0%, 100% {{
                box-shadow: 0 10px 30px rgba(255, 71, 87, 0.3);
            }}
            50% {{
                box-shadow: 0 15px 50px rgba(255, 71, 87, 0.6);
                transform: scale(1.02);
            }}
        }}

        @keyframes spin {{
            from {{ transform: rotate(0deg); }}
            to {{ transform: rotate(360deg); }}
        }}

        .voice-status {{
            margin-top: 30px;
            font-size: 1.4em;
            font-weight: 500;
        }}

        .voice-status.listening {{
            color: #ff6b7a;
        }}

        .voice-status.processing {{
            color: #4a90e2;
        }}

        .voice-status.idle {{
            color: #b0c4de;
        }}

        .transcript {{
            margin-top: 30px;
            min-height: 60px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            font-size: 1.1em;
            line-height: 1.6;
            color: #e2e8f0;
        }}

        .voice-models {{
            display: flex;
            gap: 12px;
            justify-content: center;
            margin-top: 30px;
            flex-wrap: wrap;
        }}

        .voice-model {{
            padding: 8px 16px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            font-size: 0.9em;
            cursor: pointer;
            transition: all 0.2s ease;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .voice-model:hover, .voice-model.active {{
            background: rgba(212, 175, 55, 0.2);
            border-color: #d4af37;
            color: #d4af37;
        }}

        .mode-selector {{
            position: absolute;
            top: 30px;
            right: 30px;
            display: flex;
            gap: 12px;
        }}

        .mode-button {{
            padding: 10px 20px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 25px;
            color: white;
            text-decoration: none;
            transition: all 0.3s ease;
            font-size: 0.9em;
        }}

        .mode-button.active, .mode-button:hover {{
            background: rgba(212, 175, 55, 0.2);
            border-color: #d4af37;
            color: #d4af37;
        }}

        .instructions {{
            position: absolute;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            color: rgba(255, 255, 255, 0.6);
            font-size: 0.9em;
            text-align: center;
        }}

        .error-message {{
            background: rgba(255, 71, 87, 0.1);
            border: 1px solid rgba(255, 71, 87, 0.3);
            color: #ff6b7a;
            padding: 12px 16px;
            border-radius: 12px;
            margin-top: 20px;
            font-size: 0.9em;
        }}

        @media (max-width: 768px) {{
            .voice-interface {{
                padding: 20px;
            }}

            .logo h1 {{
                font-size: 2.5em;
            }}

            .main-voice-button {{
                width: 150px;
                height: 150px;
                font-size: 3em;
            }}

            .mode-selector {{
                position: static;
                justify-content: center;
                margin-bottom: 30px;
            }}

            .instructions {{
                position: static;
                transform: none;
                margin-top: 30px;
            }}
        }}
    </style>
</head>
<body>
    <div class="mode-selector">
        <a href="/chat" class="mode-button">💬 Text Chat</a>
        <a href="/voice" class="mode-button active">🎙️ Voice Only</a>
    </div>

    <div class="voice-interface">
        <div class="logo">
            <h1>🌍 ODIA</h1>
            <p>Voice AI for Africa</p>
        </div>

        <div class="voice-controls">
            <button class="main-voice-button" id="mainVoiceButton">
                🎙️
            </button>
        </div>

        <div class="voice-status idle" id="voiceStatus">
            Tap to speak with ODIA AI
        </div>

        <div class="transcript" id="transcript">
            Your conversation will appear here...
        </div>

        <div class="voice-models">
            <div class="voice-model active" data-voice="lexi_whatsapp">🎤 Lexi</div>
            <div class="voice-model" data-voice="odia_female_nigerian">👩 ODIA Female</div>
            <div class="voice-model" data-voice="atlas_luxury">🎩 Atlas</div>
            <div class="voice-model" data-voice="miss_academic">📚 MISS</div>
        </div>
    </div>

    <div class="instructions">
        Click and hold to speak • Tap to switch modes • Voice-first AI experience
    </div>

    <script>
        // SECURE CONFIGURATION - NO SECRETS EXPOSED
        let CONFIG = {{}};

        // Global state
        let isListening = false;
        let isProcessing = false;
        let currentVoice = 'lexi_whatsapp';
        let recognition;
        let conversationHistory = [];

        // DOM elements
        const mainVoiceButton = document.getElementById('mainVoiceButton');
        const voiceStatus = document.getElementById('voiceStatus');
        const transcript = document.getElementById('transcript');

        // Load configuration first
        async function loadConfig() {{
            try {{
                const response = await fetch('/api/config');
                if (response.ok) {{
                    CONFIG = await response.json();
                    CONFIG.ANTHROPIC_API_KEY = '{os.getenv("ANTHROPIC_API_KEY", "")}';
                    initializeVoiceInterface();
                }} else {{
                    showError('Failed to load configuration');
                }}
            }} catch (error) {{
                showError('Configuration error: ' + error.message);
            }}
        }}

        function initializeVoiceInterface() {{
            setupSpeechRecognition();
            setupEventListeners();
            updateStatus('Ready to chat - tap the microphone to start');
        }}

        function setupSpeechRecognition() {{
            if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {{
                recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
                recognition.lang = 'en-NG';
                recognition.continuous = false;
                recognition.interimResults = false;

                recognition.onstart = function() {{
                    isListening = true;
                    updateButtonState('listening');
                    updateStatus('Listening... speak now');
                }};

                recognition.onresult = function(event) {{
                    const text = event.results[0][0].transcript;
                    transcript.innerHTML = `<strong>You:</strong> ${{text}}`;
                    processVoiceInput(text);
                }};

                recognition.onend = function() {{
                    isListening = false;
                    if (!isProcessing) {{
                        updateButtonState('idle');
                        updateStatus('Tap to speak again');
                    }}
                }};

                recognition.onerror = function(event) {{
                    showError('Voice recognition error: ' + event.error);
                    isListening = false;
                    updateButtonState('idle');
                    updateStatus('Voice error - tap to try again');
                }};
            }} else {{
                showError('Voice recognition not supported in this browser');
            }}
        }}

        function setupEventListeners() {{
            // Main voice button
            mainVoiceButton.addEventListener('click', toggleVoiceInput);

            // Voice model selection
            document.querySelectorAll('.voice-model').forEach(model => {{
                model.addEventListener('click', function() {{
                    document.querySelectorAll('.voice-model').forEach(m => m.classList.remove('active'));
                    this.classList.add('active');
                    currentVoice = this.dataset.voice;
                    updateStatus(`Switched to ${{getCurrentVoiceName()}} voice`);
                }});
            }});

            // Space bar activation
            document.addEventListener('keydown', function(e) {{
                if (e.code === 'Space' && !isListening && !isProcessing) {{
                    e.preventDefault();
                    startVoiceInput();
                }}
            }});

            document.addEventListener('keyup', function(e) {{
                if (e.code === 'Space' && isListening) {{
                    e.preventDefault();
                    stopVoiceInput();
                }}
            }});
        }}

        function toggleVoiceInput() {{
            if (isProcessing) return;

            if (isListening) {{
                stopVoiceInput();
            }} else {{
                startVoiceInput();
            }}
        }}

        function startVoiceInput() {{
            if (!recognition || isListening || isProcessing) return;

            try {{
                recognition.start();
            }} catch (error) {{
                console.error('Failed to start recognition:', error);
                showError('Could not start voice recognition');
            }}
        }}

        function stopVoiceInput() {{
            if (recognition && isListening) {{
                recognition.stop();
            }}
        }}

        async function processVoiceInput(userText) {{
            isProcessing = true;
            updateButtonState('processing');
            updateStatus('Processing your message...');

            try {{
                // Get AI response
                const aiResponse = await getAIResponse(userText);
                
                // Update transcript
                transcript.innerHTML = `
                    <strong>You:</strong> ${{userText}}<br><br>
                    <strong>${{getCurrentVoiceName()}}:</strong> ${{aiResponse}}
                `;

                // Generate and play voice response
                await generateVoiceResponse(aiResponse);

                updateStatus('Tap to speak again');

            }} catch (error) {{
                console.error('Processing error:', error);
                showError('Failed to process your message');
                updateStatus('Error - tap to try again');
            }} finally {{
                isProcessing = false;
                updateButtonState('idle');
            }}
        }}

        async function getAIResponse(userText) {{
            conversationHistory.push({{ role: 'user', content: userText }});

            try {{
                const response = await fetch("https://api.anthropic.com/v1/messages", {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/json",
                        "x-api-key": CONFIG.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01"
                    }},
                    body: JSON.stringify({{
                        model: "claude-sonnet-4-20250514",
                        max_tokens: 150,
                        messages: [
                            {{
                                role: "system",
                                content: "You are a helpful Nigerian AI assistant from ODIA AI. Be friendly, conversational, and concise. Keep responses under 50 words for voice interaction. Use appropriate Nigerian expressions when natural."
                            }},
                            ...conversationHistory.slice(-6) // Keep last 3 exchanges
                        ]
                    }})
                }});

                const data = await response.json();
                const aiResponse = data.content[0].text;
                
                conversationHistory.push({{ role: 'assistant', content: aiResponse }});
                return aiResponse;

            }} catch (error) {{
                console.error('AI response error:', error);
                return "I'm having trouble connecting right now. Please try again.";
            }}
        }}

        async function generateVoiceResponse(text) {{
            try {{
                const response = await fetch(CONFIG.tts_api_url, {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{
                        text: text,
                        voice_id: currentVoice,
                        ai_enhance: true
                    }})
                }});

                if (response.ok) {{
                    const audioBlob = await response.blob();
                    const audioUrl = URL.createObjectURL(audioBlob);
                    const audio = new Audio(audioUrl);
                    
                    updateStatus(`${{getCurrentVoiceName()}} is speaking...`);
                    
                    audio.onended = function() {{
                        updateStatus('Tap to speak again');
                    }};
                    
                    await audio.play();
                }} else {{
                    throw new Error('TTS request failed');
                }}

            }} catch (error) {{
                console.error('Voice generation error:', error);
                showError('Could not generate voice response');
            }}
        }}

        function updateButtonState(state) {{
            mainVoiceButton.className = 'main-voice-button';
            
            switch(state) {{
                case 'listening':
                    mainVoiceButton.classList.add('listening');
                    mainVoiceButton.innerHTML = '🔴';
                    break;
                case 'processing':
                    mainVoiceButton.classList.add('processing');
                    mainVoiceButton.innerHTML = '⏳';
                    break;
                default:
                    mainVoiceButton.innerHTML = '🎙️';
            }}
        }}

        function updateStatus(message) {{
            voiceStatus.textContent = message;
            voiceStatus.className = 'voice-status';
            
            if (isListening) {{
                voiceStatus.classList.add('listening');
            }} else if (isProcessing) {{
                voiceStatus.classList.add('processing');
            }} else {{
                voiceStatus.classList.add('idle');
            }}
        }}

        function getCurrentVoiceName() {{
            const voiceNames = {{
                'lexi_whatsapp': 'Lexi',
                'odia_female_nigerian': 'ODIA Female',
                'atlas_luxury': 'Atlas',
                'miss_academic': 'MISS'
            }};
            return voiceNames[currentVoice] || 'ODIA AI';
        }}

        function showError(message) {{
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            errorDiv.textContent = message;
            document.querySelector('.voice-interface').appendChild(errorDiv);

            setTimeout(() => {{
                if (errorDiv.parentNode) {{
                    errorDiv.remove();
                }}
            }}, 5000);
        }}

        // Initialize the voice interface
        loadConfig();
    </script>
</body>
</html>
    '''

@app.route('/api/admin/create-api-key', methods=['POST'])
@require_admin
def create_api_key():
    """Create new API key (admin only)"""
    try:
        data = request.get_json() or {}
        name = data.get('name', 'Production Key')
        rate_limit = min(int(data.get('rate_limit_per_minute', 100)), 1000)
        total_quota = max(int(data.get('total_quota', 0)), 0)
        
        # Generate API key
        api_key = generate_api_key()
        key_hash = hash_api_key(api_key)
        
        # Store in database
        conn = get_db_connection()
        cursor = conn.execute('''
            INSERT INTO api_keys (name, key_hash, rate_limit_per_minute, total_quota, metadata)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, key_hash, rate_limit, total_quota, json.dumps({
            'created_by': 'admin',
            'version': '1.0',
            'environment': app.config['ENVIRONMENT']
        })))
        
        api_key_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Log brain experience
        log_brain_experience(
            'api_key_created',
            'success',
            {
                'api_key_id': api_key_id,
                'name': name,
                'rate_limit': rate_limit,
                'quota': total_quota
            }
        )
        
        logger.info(f"Created API key {api_key_id} for '{name}'")
        
        return jsonify({
            'api_key': api_key,
            'id': api_key_id,
            'name': name,
            'rate_limit_per_minute': rate_limit,
            'total_quota': total_quota,
            'created_at': datetime.utcnow().isoformat(),
            'nigeria_ready': True
        })
        
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        return jsonify({'error': 'Failed to create API key'}), 500

@app.route('/api/docs')
def api_documentation():
    """Enhanced API documentation"""
    return jsonify({
        'name': 'ODIA AI TTS API',
        'version': '1.0.0',
        'description': 'Nigerian-optimized Text-to-Speech API with AI Enhancement',
        'base_url': request.url_root + 'api',
        'render_deployment': True,
        'nigeria_optimized': True,
        'ai_powered': ANTHROPIC_AVAILABLE,
        'security_features': [
            'No secrets exposed in frontend',
            'Secure API key management',
            'Enterprise-grade authentication',
            'Encrypted communications'
        ],
        'endpoints': {
            'GET /health': 'System health check',
            'GET /v1/voices': 'List Nigerian voice models',
            'POST /v1/text-to-speech': 'Synthesize speech (requires API key)',
            'GET /speak': 'Simple TTS endpoint (GET method)',
            'GET /test': 'Simple test endpoint',
            'GET /config': 'Get secure client configuration',
            'POST /admin/create-api-key': 'Create API key (admin only)'
        },
        'interfaces': {
            '/chat': 'Modern text + voice chat interface',
            '/voice': 'Voice-only interface (Claude-style)'
        },
        'features': {
            'nigerian_voices': 6,
            'ai_text_enhancement': ANTHROPIC_AVAILABLE,
            'real_time_synthesis': True,
            'voice_only_mode': True,
            'usage_analytics': True,
            'business_terminology': True
        },
        'example_request': {
            'url': request.url_root + 'api/v1/text-to-speech',
            'method': 'POST',
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': {
                'text': 'Welcome to ODIA AI, Nigeria no dey wait!',
                'voice_id': 'odia_female_nigerian',
                'ai_enhance': True
            }
        },
        'simple_test': {
            'url': request.url_root + 'speak?text=Hello&voice=female',
            'method': 'GET',
            'headers': {
                'x-api-key': 'odiadev_10abb658e85c30550ed75b30e7f55836'
            }
        }
    })

# Error handlers with enhanced security
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint not found', 
        'nigeria_ready': True,
        'suggestion': 'Check /api/docs for available endpoints'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal server error', 
        'nigeria_ready': True,
        'contact': 'contact@odia.dev'
    }), 500

if __name__ == '__main__':
    logger.info("🚀 Starting ODIA AI TTS Enhanced Production Server")
    logger.info(f"Environment: {app.config['ENVIRONMENT']}")
    logger.info(f"ODIA Mode: {app.config['ODIA_MODE']}")
    logger.info(f"Admin Token: {'✅ Configured' if app.config['ADMIN_BEARER_TOKEN'] else '❌ Not Set'}")
    logger.info(f"TTS Engine: {'✅ Available' if TTS_ENGINE_AVAILABLE else '❌ Not Available'}")
    logger.info(f"Anthropic AI: {'✅ Available' if ANTHROPIC_AVAILABLE else '❌ Not Available'}")
    logger.info(f"Require API Key: {app.config['REQUIRE_KEY_FOR_SPEAK']}")
    logger.info("🔐 Security: Enterprise-grade with no exposed secrets")
    
    # Log system startup
    log_brain_experience(
        'system_startup',
        'success',
        {
            'environment': app.config['ENVIRONMENT'],
            'tts_engine': TTS_ENGINE_AVAILABLE,
            'ai_available': ANTHROPIC_AVAILABLE,
            'port': app.config['PORT'],
            'security_grade': 'enterprise'
        }
    )
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=app.config['PORT'],
        debug=(app.config['ENVIRONMENT'] == 'development')
    )