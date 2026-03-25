import requests

def test_upload(filepath, mime_type):
    print(f"Testing {filepath} ({mime_type})...")
    with open(filepath, 'rb') as f:
        files = {'file': (filepath.split('/')[-1], f, mime_type)}
        response = requests.post('http://127.0.0.1:8000/upload', files=files)
        print(f"Status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return False
        return True

test_upload('test_audio/lecture.wav', 'audio/wav')
test_upload('test_audio/lecture.m4a', 'audio/mp4')
