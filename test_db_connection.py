import os
import asyncio
from dotenv import load_dotenv
from infrastructure.supabase_logger import _get_client as get_supabase_client

load_dotenv(".env")

async def test_rpc():
    supabase = get_supabase_client()
    if not supabase:
        print("Supabase client not initialized.")
        return

    # Mock embedding (384 dimensions for all-MiniLM-L6-v2)
    mock_emb = [0.0] * 384
    
    try:
        print("Calling RPC 'match_documents'...")
        response = supabase.rpc("match_documents", {
            "query_embedding": mock_emb,
            "match_threshold": 0.40,
            "match_count": 3
        }).execute()
        print("RPC Response Data:", response.data)
    except Exception as e:
        print(f"RPC Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_rpc())
