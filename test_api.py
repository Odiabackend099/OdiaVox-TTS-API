# ODIA AI TTS API Test Script
# Run this after starting the server to test the API

import requests
import json

# Server URL
BASE_URL = "http://localhost:5000"
ADMIN_TOKEN = "odia-admin-2025"

def test_health():
    """Test health endpoint"""
    print("🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        print(f"Health Check: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {data['status']}")
            print(f"✅ TTS Engine: {data['services']['tts_engine']}")
            print(f"✅ Database: {data['services']['database']}")
            return True
        else:
            print(f"❌ Health check failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def list_voices():
    """List available voices"""
    print("\n🎤 Listing available voices...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/voices")
        if response.status_code == 200:
            data = response.json()
            voices = data['voices']
            print(f"✅ Found {len(voices)} voice models:")
            for voice in voices:
                print(f"   • {voice['name']} ({voice['voice_id']}) - {voice['use_case']}")
            return voices
        else:
            print(f"❌ Failed to list voices: {response.text}")
            return []
    except Exception as e:
        print(f"❌ Voice listing error: {e}")
        return []

def create_api_key():
    """Create a test API key"""
    print("\n🔑 Creating test API key...")
    headers = {
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "name": "ODIA Test API Key",
        "rate_limit_per_minute": 100,
        "total_quota": 0
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/admin/create-api-key", 
                               headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API Key created successfully!")
            print(f"   ID: {result['id']}")
            print(f"   Name: {result['name']}")
            print(f"   Key: {result['api_key']}")
            return result['api_key']
        else:
            print(f"❌ Failed to create API key: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ API key creation error: {e}")
        return None

def test_tts(api_key):
    """Test TTS synthesis"""
    print(f"\n🎵 Testing TTS synthesis...")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    test_cases = [
        {
            "text": "Hello! Welcome to ODIA AI, Nigeria's premier voice technology platform.",
            "voice_id": "odia_female_nigerian",
            "filename": "test_odia_female.wav"
        },
        {
            "text": "Good day! How can we assist you with your business today?",
            "voice_id": "odia_male_nigerian", 
            "filename": "test_odia_male.wav"
        },
        {
            "text": "Hey! I'm Lexi, your friendly WhatsApp assistant.",
            "voice_id": "lexi_whatsapp",
            "filename": "test_lexi.wav"
        }
    ]
    
    success_count = 0
    
    for test_case in test_cases:
        try:
            print(f"   Testing {test_case['voice_id']}...")
            
            data = {
                "text": test_case["text"],
                "voice_id": test_case["voice_id"]
            }
            
            response = requests.post(f"{BASE_URL}/api/v1/text-to-speech", 
                                   headers=headers, json=data)
            
            if response.status_code == 200:
                print(f"   ✅ Synthesis successful: {len(response.content)} bytes")
                
                # Save audio file
                with open(test_case["filename"], "wb") as f:
                    f.write(response.content)
                print(f"   ✅ Audio saved to {test_case['filename']}")
                success_count += 1
            else:
                print(f"   ❌ Synthesis failed: {response.status_code}")
                print(f"      Response: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Error testing {test_case['voice_id']}: {e}")
    
    return success_count

def test_usage_stats(api_key):
    """Test usage statistics"""
    print(f"\n📊 Testing usage statistics...")
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/usage", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Usage stats retrieved:")
            print(f"   API Key: {data['name']}")
            print(f"   Usage Count: {data['usage_count']}")
            print(f"   Bytes Out: {data['bytes_out']}")
            print(f"   Rate Limit: {data['rate_limit_per_minute']}/min")
            return True
        else:
            print(f"❌ Failed to get usage stats: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Usage stats error: {e}")
        return False

def main():
    print("🧪 ODIA AI TTS API Test Suite")
    print("=" * 50)
    
    # Test health
    if not test_health():
        print("❌ Health check failed. Make sure server is running at localhost:5000")
        return
    
    # List voices
    voices = list_voices()
    if not voices:
        print("❌ No voices available")
        return
    
    # Create API key
    api_key = create_api_key()
    if not api_key:
        print("❌ Failed to create API key. Check admin token.")
        return
    
    # Test TTS synthesis
    success_count = test_tts(api_key)
    
    # Test usage stats
    test_usage_stats(api_key)
    
    # Summary
    print(f"\n🎉 Test Suite Complete!")
    print(f"=" * 50)
    print(f"✅ Voices tested: {success_count}/3")
    print(f"🔑 Your API key: {api_key}")
    print(f"📝 Keep this key secure for production use")
    print(f"🎵 Audio files saved in current directory")
    
    if success_count == 3:
        print(f"\n🚀 All tests passed! ODIA AI TTS is ready for production!")
    else:
        print(f"\n⚠️ Some tests failed, but basic functionality is working")

if __name__ == "__main__":
    main()