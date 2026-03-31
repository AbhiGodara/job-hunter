"""
Quick test script to check if your Gemini API key works.
Run this directly: python test_gemini.py
"""
import os
from dotenv import load_dotenv
load_dotenv(override=True)

api_key = os.environ.get("GEMINI_API_KEY", "")
print(f"API Key found: {'YES (' + api_key[:10] + '...)' if api_key else 'NO'}")

if not api_key:
    print("❌ No GEMINI_API_KEY found in .env file!")
    exit(1)

# Test 1: Direct google-genai SDK call
print("\n--- Test 1: Direct Google GenAI SDK ---")
try:
    from google import genai
    client = genai.Client(api_key=api_key)
    
    # Try multiple models
    for model_name in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents="Say hello in one word."
            )
            print(f"  ✅ {model_name}: {response.text.strip()}")
        except Exception as e:
            print(f"  ❌ {model_name}: {str(e)[:100]}")

except ImportError:
    print("  ❌ google-genai not installed. Run: pip install google-genai")
except Exception as e:
    print(f"  ❌ Error: {e}")

# Test 2: Via LiteLLM (what CrewAI uses)
print("\n--- Test 2: Via LiteLLM (CrewAI's engine) ---")
try:
    import litellm
    for model_name in ["gemini/gemini-1.5-flash", "gemini/gemini-2.0-flash-lite"]:
        try:
            response = litellm.completion(
                model=model_name,
                messages=[{"role": "user", "content": "Say hello in one word."}],
                api_key=api_key,
            )
            print(f"  ✅ {model_name}: {response.choices[0].message.content.strip()}")
        except Exception as e:
            print(f"  ❌ {model_name}: {str(e)[:150]}")
except ImportError:
    print("  ❌ litellm not installed")

print("\n--- Done ---")
