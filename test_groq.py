"""Test CrewAI LLM class directly - same way app.py uses it"""
import os
from dotenv import load_dotenv
load_dotenv(override=True)

print(f"GROQ_API_KEY in env: {'YES (' + os.environ.get('GROQ_API_KEY', '')[:15] + '...)' if os.environ.get('GROQ_API_KEY') else 'NO'}")

# Test 1: litellm direct (WORKS - we know this)
print("\n--- Test 1: litellm direct ---")
try:
    import litellm
    resp = litellm.completion(
        model="groq/llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "Say hi"}],
        api_key=os.environ.get("GROQ_API_KEY"),
    )
    print(f"  ✅ litellm: {resp.choices[0].message.content.strip()}")
except Exception as e:
    print(f"  ❌ litellm: {e}")

# Test 2: CrewAI LLM with api_key param
print("\n--- Test 2: CrewAI LLM (with api_key param) ---")
try:
    from crewai import LLM
    llm = LLM(model="groq/llama-3.3-70b-versatile", api_key=os.environ.get("GROQ_API_KEY"))
    result = llm.call(messages=[{"role": "user", "content": "Say hi in one word"}])
    print(f"  ✅ CrewAI LLM: {result}")
except Exception as e:
    print(f"  ❌ CrewAI LLM: {str(e)[:200]}")

# Test 3: CrewAI LLM without api_key (relies on env var)
print("\n--- Test 3: CrewAI LLM (env var only) ---")
try:
    from crewai import LLM
    llm = LLM(model="groq/llama-3.3-70b-versatile")
    result = llm.call(messages=[{"role": "user", "content": "Say hi in one word"}])
    print(f"  ✅ CrewAI LLM (env): {result}")
except Exception as e:
    print(f"  ❌ CrewAI LLM (env): {str(e)[:200]}")

print("\n--- Done ---")
