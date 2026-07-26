import asyncio
import os
from dotenv import load_dotenv

# Load environment variables (needed for GROQ_API_KEY and Database connection)
load_dotenv()

from lib.prisma_client import db
from lib.code_switch.code_switch_text import TextCodeSwitchDetector
from services.code_switch_service import log_detected_word, get_word_list

async def main():
    print("=== Speeky Code-Switch Interactive Test (US-152) ===\n")
    
    # Check if Groq is configured
    from lib import llm_client
    if not llm_client.is_configured():
        print("WARNING: GROQ_API_KEY is not set or configured. Groq calls will be skipped.")
        return

    # Connect to the database
    await db.connect()
    try:
        user_id = "interactive_test_user"
        
        # Get custom input from user
        text = input("Enter a sentence with a mixed Urdu/local word (e.g. 'Can you send it jaldi?'): ")
        if not text.strip():
            print("No input provided. Exiting.")
            return

        print(f"\n[1] Detecting code-switches via Groq for: '{text}'...")
        detector = TextCodeSwitchDetector()
        detection = await detector.detect(text)
        
        flagged_words = detection.get("flagged", [])
        if not flagged_words:
            print("No code-switched words were detected.")
        else:
            print(f"Detected: {flagged_words}")
            
            print("\n[2] Logging detected words to your list...")
            for flagged in flagged_words:
                await log_detected_word(
                    user_id=user_id,
                    word=flagged["token"],
                    english_equivalent=flagged["suggestion"],
                    context_sentence=text
                )
                print(f"Logged: '{flagged['token']}' -> '{flagged['suggestion']}'")
        
        # Display the current list
        print("\n[3] Fetching your current personal word list:")
        res = await get_word_list(user_id)
        if not res.words:
            print(res.empty_state_message)
        else:
            for w in res.words:
                print(f"- {w.word} -> English: {w.english_equivalent} | Frequency: {w.frequency} | Contexts: {w.context_sentences}")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        # Disconnect from database
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
