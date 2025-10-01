import React, { useRef, useState } from 'react';
import './FileUploader.css';

const FileUploader = ({ onFileUpload, sessionId }) => {
  const fileInputRef = useRef();
  const [isUploading, setIsUploading] = useState(false);

  const handleFileSelect = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setIsUploading(true);
    
    try {
      const formData = new FormData();
      formData.append('log_file', file);

      // Добавляем session_id если есть
      if (sessionId) {
        formData.append('session_id', sessionId);
      }

      const uploadResponse = await fetch('/api/upload/', {
        method: 'POST',
        body: formData,
      });

      if (!uploadResponse.ok) {
        const errorText = await uploadResponse.text();
        throw new Error(`HTTP error! status: ${uploadResponse.status}, message: ${errorText}`);
      }

      const uploadResult = await uploadResponse.json();
      
      if (uploadResult.status === 'success') {
        // Передаем результат загрузки в родительский компонент
        onFileUpload(uploadResult);
      } else {
        throw new Error(uploadResult.message || 'Upload failed');
      }
      
    } catch (error) {
      console.error('Upload error:', error);
      alert(`Error uploading file: ${error.message}`);
    } finally {
      setIsUploading(false);
      // Сбрасываем input чтобы можно было загрузить тот же файл снова
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="file-uploader">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        accept=".json,.log,.txt"
        style={{ display: 'none' }}
        disabled={isUploading}
      />
      <button 
        className={`upload-button ${isUploading ? 'uploading' : ''}`}
        onClick={handleButtonClick}
        disabled={isUploading}
      >
        {isUploading ? (
          <>
            <div className="spinner"></div>
            Parsing...
          </>
        ) : (
          <>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" strokeWidth="2"/>
              <polyline points="14,2 14,8 20,8" stroke="currentColor" strokeWidth="2"/>
              <line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" strokeWidth="2"/>
              <line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" strokeWidth="2"/>
              <polyline points="10,9 9,9 8,9" stroke="currentColor" strokeWidth="2"/>
            </svg>
            Upload Terraform Logs
          </>
        )}
      </button>
    </div>
  );
};

export default FileUploader;