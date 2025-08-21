#!/usr/bin/env python3
"""
ODIA AI TTS Enhanced Production Backend
Nigerian Voice Technology Platform with AI Integration
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

try:
    import openai
    OPENAI_AVAILABLE = bool(os.getenv('OPENAI_API_KEY'))
except ImportError:
    OPENAI_AVAILABLE = False

# Configure logging for production
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("ODIA.Production")

# Initialize Flask app
app = Flask(__name__)

# Enhanced production configuration
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
    
    # Security
    'ADMIN_BEARER_TOKEN': os.getenv('ADMIN_BEARER_TOKEN'),
    'KEY_PEPPER': os.getenv('KEY_PEPPER', 'odia-default-pepper'),
    'WEBHOOK_SECRET': os.getenv('WEBHOOK_SECRET'),
    
    # TTS settings
    'TTS_ENGINE': os.getenv('TTS_ENGINE', 'edge-tts'),
    'VOICE_CACHE_ENABLED': os.getenv('VOICE_CACHE_ENABLED', 'true').lower() == 'true',
    'AUDIO_SAMPLE_RATE': int(os.getenv('AUDIO_SAMPLE_RATE', '22050')),
    
    # AI settings
    'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
    
    # ODIA specific
    'ODIA_MODE': os.getenv('ODIA_MODE', 'production'),
    'REQUIRE_KEY_FOR_SPEAK': os.getenv('REQUIRE_KEY_FOR_SPEAK', '1') == '1'
})

# Enable CORS
cors_origins = os.getenv('ALLOWED_ORIGINS', '*')
if cors_origins == '*':
    CORS(app, origins=["*"])
else:
    CORS(app, origins=cors_origins.split(','))

# Initialize AI clients
if ANTHROPIC_AVAILABLE:
    anthropic_client = anthropic.Anthropic(api_key=app.config['ANTHROPIC_API_KEY'])
    logger.info("✅ Anthropic AI client initialized")

if OPENAI_AVAILABLE:
    openai.api_key = app.config['OPENAI_API_KEY']
    logger.info("✅ OpenAI client initialized")

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
            'business_ready': True
        },
        'endpoints': {
            'health': '/api/health',
            'voices': '/api/v1/voices',
            'synthesis': '/api/v1/text-to-speech',
            'documentation': '/api/docs',
            'admin': '/api/admin/*'
        },
        'ai_capabilities': {
            'anthropic': ANTHROPIC_AVAILABLE,
            'openai': OPENAI_AVAILABLE,
            'text_enhancement': ANTHROPIC_AVAILABLE
        },
        'tts_engine': TTS_ENGINE_AVAILABLE
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
        'anthropic': 'ok' if ANTHROPIC_AVAILABLE else 'unavailable',
        'openai': 'ok' if OPENAI_AVAILABLE else 'unavailable'
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
        
        # Log brain experience
        log_brain_experience(
            'tts_synthesis',
            'error',
            {
                'error': error_msg,
                'voice_id': voice_id if 'voice_id' in locals() else 'unknown',
                'duration_ms': duration_ms
            }
        )
        
        logger.error(f"TTS synthesis error: {e}")
        return jsonify({
            'error': 'TTS synthesis failed',
            'request_id': request_id
        }), 500

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
        'authentication': 'Bearer token required for synthesis',
        'endpoints': {
            'GET /health': 'System health check',
            'GET /v1/voices': 'List Nigerian voice models',
            'POST /v1/text-to-speech': 'Synthesize speech (requires API key)',
            'POST /admin/create-api-key': 'Create API key (admin only)'
        },
        'features': {
            'nigerian_voices': 6,
            'ai_text_enhancement': ANTHROPIC_AVAILABLE,
            'real_time_synthesis': True,
            'usage_analytics': True,
            'business_terminology': True
        },
        'example_request': {
            'url': request.url_root + 'api/v1/text-to-speech',
            'method': 'POST',
            'headers': {
                'Authorization': 'Bearer odia_YOUR_API_KEY',
                'Content-Type': 'application/json'
            },
            'body': {
                'text': 'Welcome to ODIA AI, Nigeria no dey wait!',
                'voice_id': 'odia_female_nigerian',
                'ai_enhance': True
            }
        },
        'admin_token': f"Bearer {app.config['ADMIN_BEARER_TOKEN']}"
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found', 'nigeria_ready': True}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error', 'nigeria_ready': True}), 500

if __name__ == '__main__':
    logger.info("🚀 Starting ODIA AI TTS Enhanced Production Server")
    logger.info(f"Environment: {app.config['ENVIRONMENT']}")
    logger.info(f"ODIA Mode: {app.config['ODIA_MODE']}")
    logger.info(f"Admin Token: {app.config['ADMIN_BEARER_TOKEN']}")
    logger.info(f"TTS Engine: {'✅ Available' if TTS_ENGINE_AVAILABLE else '❌ Not Available'}")
    logger.info(f"Anthropic AI: {'✅ Available' if ANTHROPIC_AVAILABLE else '❌ Not Available'}")
    logger.info(f"OpenAI: {'✅ Available' if OPENAI_AVAILABLE else '❌ Not Available'}")
    logger.info(f"Require API Key: {app.config['REQUIRE_KEY_FOR_SPEAK']}")
    
    # Log system startup
    log_brain_experience(
        'system_startup',
        'success',
        {
            'environment': app.config['ENVIRONMENT'],
            'tts_engine': TTS_ENGINE_AVAILABLE,
            'ai_available': ANTHROPIC_AVAILABLE,
            'port': app.config['PORT']
        }
    )
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=app.config['PORT'],
        debug=(app.config['ENVIRONMENT'] == 'development')
    )