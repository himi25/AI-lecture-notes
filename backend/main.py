import os
import shutil
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv(override=True)

app = FastAPI(title="AI Lecture Notes Generator MVP")

# Add CORS middleware to allow requests from the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins e.g., ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini Client
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    print("Warning: GEMINI_API_KEY not configured on server.")

class NotesResponse(BaseModel):
    transcript: str
    notes: str

@app.post("/upload", response_model=NotesResponse)
async def upload_audio(file: UploadFile = File(...)):
    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="Gemini API key not configured on server.")

    # Validate file type (basic check)
    allowed_types = ["audio/mpeg", "audio/mp4", "audio/wav", "audio/x-m4a", "audio/webm", "audio/mp3", "video/mp4", "audio/ogg"]
    if file.content_type not in allowed_types and not file.filename.endswith(('.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm', '.ogg')):
         raise HTTPException(status_code=400, detail="Invalid file type. Please upload a supported audio file.")

    # Create temp directory if it doesn't exist
    os.makedirs("temp", exist_ok=True)
    temp_file_path = f"temp/{file.filename}"

    try:
        # Save the uploaded file temporarily
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 1. Convert any incoming audio to a clean AAC using macOS built-in afconvert
        # This completely bypasses Gemini's buggy video-pipeline routing for M4A/MP4 files,
        # AND keeps the file highly compressed (unlike WAV) so it uploads in 2 seconds instead of 3 minutes.
        import time
        import subprocess
        
        safe_aac_path = f"temp/{file.filename}.aac"
        try:
            subprocess.run(["afconvert", "-f", "adts", "-d", "aac", temp_file_path, safe_aac_path], check=True)
            upload_target = safe_aac_path
            mime_type = "audio/aac"
        except Exception as e:
            print(f"Conversion failed, uploading original: {e}")
            upload_target = temp_file_path
            mime_type = file.content_type

        # 2. Upload the safe file to Gemini
        uploaded_file = genai.upload_file(path=upload_target, mime_type=mime_type)
        
        # Wait for the file to finish processing before we try to generate content from it
        timeout = 180 # 3 minutes max wait time
        start_time = time.time()
        while uploaded_file.state.name == "PROCESSING":
            if time.time() - start_time > timeout:
                raise Exception("Google Gemini servers took too long to process the audio (timed out after 3 minutes). Please try a shorter lecture.")
            print("File is processing, waiting...")
            time.sleep(2)
            uploaded_file = genai.get_file(uploaded_file.name)
            
        if uploaded_file.state.name == "FAILED":
             error_detail = getattr(uploaded_file, "error", "Unknown error or unsupported format")
             raise Exception(f"Gemini failed to process the uploaded audio file. Detail: {error_detail}")

        # 3. Prompt Gemini to transcribe and format notes
        system_instruction = """
        You are an expert educational assistant. Your task is to process lecture audio and create high-quality, structured notes alongside the full transcript.
        
        You must return a raw JSON object string with TWO keys:
        1. "transcript": A string containing the full audio transcript.
        2. "notes": A string containing structured markdown notes. Format the notes using Markdown including these sections:
           - **Summary**: A brief 2-3 sentence overview of the main topic.
           - **Key Topics**: A bulleted list of the main subjects covered.
           - **Detailed Notes**: Structured bullet points capturing the important concepts, explanations, and details.
           - **Important Definitions/Terms**: A list of key terminology and their definitions mentioned in the lecture.
           
        CRITICAL: Ensure your output is purely JSON. Do not wrap it in ```json or any markdown blocks.
        """
        
        # Use gemini-2.5-flash as it is fast and supports audio and JSON mode out of the box
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        response = model.generate_content(
            [system_instruction, "Please provide the JSON for this audio lecture:", uploaded_file],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=NotesResponse,
                max_output_tokens=8192
            )
        )
        
        # Clean up Gemini file storage
        try:
            genai.delete_file(uploaded_file.name)
        except Exception as e:
             print(f"Failed to delete file from Gemini storage: {e}")

        # 4. Check for safety or copyright blocks
        if response.candidates and response.candidates[0].finish_reason.name != "STOP":
            reason = response.candidates[0].finish_reason.name
            if reason == "RECITATION":
                raise Exception("Gemini blocked the response because it detected copyrighted material in the lecture. Try uploading a different lecture.")
            raise Exception(f"Gemini blocked the response due to its safety guidelines. Reason: {reason}")

        # Parse the JSON response
        result = json.loads(response.text)
        
        transcript_text = result.get("transcript", "Transcript could not be generated.")
        notes_text = result.get("notes", "Notes could not be generated.")

        return NotesResponse(transcript=transcript_text, notes=notes_text)

    except json.JSONDecodeError as e:
        raw_text = response.text if hasattr(response, 'text') else 'No text found'
        print(f"Error parsing Gemini response: {e}\nRaw text: {raw_text}")
        raise HTTPException(status_code=500, detail=f"Failed to parse the response from Gemini. Raw: {raw_text[:200]}")
    except Exception as e:
        print(f"Error processing audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up the local temporary files
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if 'safe_aac_path' in locals() and os.path.exists(safe_aac_path):
             os.remove(safe_aac_path)

@app.get("/")
def read_root():
    return {"message": "AI Lecture Notes Generator API is running with Gemini. POST audio to /upload"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
