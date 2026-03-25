import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv(override=True)
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

print("Uploading aac with mime_type='audio/aac'...")
try:
    file_aac = genai.upload_file(path="test_audio/lecture.aac", mime_type="audio/aac")
    print(f"Uploaded as {file_aac.name}, State: {file_aac.state.name}")
except Exception as e:
    print(f"Failed audio/aac: {e}")
