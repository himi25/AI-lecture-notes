import React, { useState, useRef } from 'react';
import { uploadAudio } from '../api';

const Upload = ({ onResults }) => {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError('');
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select an audio file first.');
      return;
    }

    setLoading(true);
    setError('');
    setProgress(0);

    let progressInterval;

    try {
      const data = await uploadAudio(file, (progressEvent) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        // Upload progress (0 -> 40%)
        setProgress(Math.floor(percentCompleted * 0.4));
        
        if (percentCompleted === 100 && !progressInterval) {
           // File reached backend, now we wait for AI processing (40 -> 95%)
           let currentProgress = 40;
           progressInterval = setInterval(() => {
               currentProgress += (95 - currentProgress) * 0.08; // Smooth asymptotic approach to 95%
               setProgress(Math.floor(currentProgress));
           }, 1000);
        }
      });
      clearInterval(progressInterval);
      setProgress(100);
      onResults(data);
    } catch (err) {
      clearInterval(progressInterval);
      setError(err.message || 'Error uploading file.');
    } finally {
      setLoading(false);
    }
  };

  const clearFile = () => {
    setFile(null);
    if (fileInputRef.current) {
        fileInputRef.current.value = '';
    }
  };

  return (
    <div className="upload-container glass-card">
      <h2 className="title">Upload Lecture Audio</h2>
      <p className="subtitle">Supported formats: MP3, MP4, WAV, M4A</p>

      <div className="file-input-wrapper">
        <input
          type="file"
          accept="audio/*,video/mp4"
          onChange={handleFileChange}
          id="file-upload"
          disabled={loading}
          ref={fileInputRef}
          className="file-input"
        />
        <label htmlFor="file-upload" className={`file-label ${file ? 'has-file' : ''}`}>
          {file ? (
             <div className="file-info">
                 <span className="icon">🎵</span>
                 <span className="filename">{file.name}</span>
             </div>
          ) : (
             <div className="file-info">
                <span className="icon">📁</span>
                <span>Choose a file or drag it here</span>
             </div>
          )}
        </label>
        {file && !loading && (
          <button className="clear-btn" onClick={clearFile} title="Remove file">✕</button>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      {loading && (
        <div className="progress-container">
          <div className="progress-bar-bg">
            <div className="progress-bar-fill" style={{ width: `${progress}%` }}></div>
          </div>
          <p className="progress-text">{progress < 40 ? 'Uploading Audio...' : 'AI Analyzing Lecture...'} {progress}%</p>
        </div>
      )}

      <button
        className={`generate-btn ${loading ? 'loading' : ''}`}
        onClick={handleUpload}
        disabled={!file || loading}
      >
        {loading ? (
          <>
            <span className="spinner"></span>
            Processing Audio...
          </>
        ) : (
          'Generate Notes'
        )}
      </button>
    </div>
  );
};

export default Upload;
