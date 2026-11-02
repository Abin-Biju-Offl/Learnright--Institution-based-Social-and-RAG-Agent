import React, { useState, useEffect, useRef } from 'react';

/**
 * TextbookUploadTab
 * Allows parents to securely upload custom textbooks, automatically screen them for
 * under-18 appropriateness, chunk them into semantic sections, and embed them into
 * the vector store for their child to query.
 */
export default function TextbookUploadTab({ token, onBookUploaded }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [grade, setGrade] = useState(10);
  const [subject, setSubject] = useState('Physics');
  const [bookTitle, setBookTitle] = useState('');
  const [chapterNumber, setChapterNumber] = useState(1);
  const [chapterTitle, setChapterTitle] = useState('');

  const [isUploading, setIsUploading] = useState(false);
  const [uploadStep, setUploadStep] = useState(0); // 0=idle, 1=validating, 2=chunking, 3=embedding, 4=done
  const [errorMessage, setErrorMessage] = useState('');
  const [successInfo, setSuccessInfo] = useState(null);

  const [uploadedBooks, setUploadedBooks] = useState([]);
  const [isLoadingBooks, setIsLoadingBooks] = useState(false);
  const [deletingCode, setDeletingCode] = useState(null);

  const fileInputRef = useRef(null);

  // Fetch list of custom uploaded textbooks
  const fetchUploadedBooks = async () => {
    setIsLoadingBooks(true);
    try {
      const res = await fetch('/api/parent/textbooks', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUploadedBooks(data.textbooks || []);
      }
    } catch (e) {
      console.warn('Could not fetch uploaded books', e);
    } finally {
      setIsLoadingBooks(false);
    }
  };

  useEffect(() => {
    fetchUploadedBooks();
  }, [token]);

  // Handle file drop / selection
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setErrorMessage('Only PDF documents are supported.');
        return;
      }
      setSelectedFile(file);
      setErrorMessage('');
      setSuccessInfo(null);
      // Auto-suggest book title from filename if empty
      if (!bookTitle) {
        const baseName = file.name.replace(/\.pdf$/i, '').replace(/[_-]/g, ' ');
        setBookTitle(baseName);
      }
    }
  };

  // Submit and upload textbook
  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessInfo(null);

    if (!selectedFile) {
      setErrorMessage('Please select a textbook PDF file.');
      return;
    }
    if (!subject.trim()) {
      setErrorMessage('Please enter a subject name (e.g. Physics, History).');
      return;
    }
    if (!bookTitle.trim()) {
      setErrorMessage('Please enter a book title.');
      return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('grade', String(grade));
    formData.append('subject', subject.trim());
    formData.append('book_title', bookTitle.trim());
    formData.append('chapter_number', String(chapterNumber || 1));
    formData.append('chapter_title', chapterTitle.trim() || `Chapter ${chapterNumber || 1}`);

    setIsUploading(true);
    setUploadStep(1);

    // Simulated progress steps for smooth UX while backend processes
    const stepTimer1 = setTimeout(() => setUploadStep(2), 700);
    const stepTimer2 = setTimeout(() => setUploadStep(3), 1600);

    try {
      const res = await fetch('/api/parent/textbook/upload', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);

      if (res.ok) {
        const result = await res.json();
        setUploadStep(4);
        setSuccessInfo(result);
        setSelectedFile(null);
        setBookTitle('');
        setChapterTitle('');
        if (fileInputRef.current) fileInputRef.current.value = '';
        fetchUploadedBooks();
        if (onBookUploaded) onBookUploaded(result);
      } else {
        const errData = await res.json().catch(() => ({}));
        setUploadStep(0);
        setErrorMessage(errData.detail || 'Failed to process and ingest textbook.');
      }
    } catch (err) {
      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);
      setUploadStep(0);
      setErrorMessage('Network or server error while uploading textbook.');
    } finally {
      setIsUploading(false);
    }
  };

  // Handle deletion of custom textbook
  const handleDeleteBook = async (bookCode) => {
    if (!window.confirm('Are you sure you want to remove this textbook from your child\'s library?')) {
      return;
    }
    setDeletingCode(bookCode);
    try {
      const res = await fetch(`/api/parent/textbook/${encodeURIComponent(bookCode)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        fetchUploadedBooks();
        if (onBookUploaded) onBookUploaded();
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || 'Failed to delete textbook.');
      }
    } catch {
      alert('Network error while deleting textbook.');
    } finally {
      setDeletingCode(null);
    }
  };

  return (
    <div className="parental-tab-pane textbook-upload-tab">
      <div className="tab-section-intro">
        <h4>Textbook Ingestion & Vector Storage</h4>
        <p>
          Upload digital textbook PDFs for your student. Every document is automatically
          moderated for under-18 safety, split into semantic knowledge chunks, and embedded
          directly into the vector space so the AI tutor answers strictly from it.
        </p>
      </div>

      {/* Success Notification Banner */}
      {successInfo && (
        <div className="upload-success-banner">
          <div className="upload-success-icon">✓</div>
          <div className="upload-success-text">
            <strong>Textbook Ingested Successfully!</strong>
            <p>
              "{successInfo.book}" (Class {successInfo.grade} {successInfo.subject}) is now indexed.
              Stored <strong>{successInfo.chunks_stored} chunks</strong> across{' '}
              <strong>{successInfo.pages_indexed} pages</strong> in vector space. Your child can now ask questions about it!
            </p>
          </div>
        </div>
      )}

      {/* Error Notification Banner */}
      {errorMessage && (
        <div className="upload-error-banner">
          <span className="error-icon">⚠️</span>
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Upload Form Card */}
      <div className="parental-settings-card upload-form-card">
        <form onSubmit={handleUploadSubmit}>
          {/* File Dropzone */}
          <div
            className={`file-dropzone ${selectedFile ? 'has-file' : ''}`}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              style={{ display: 'none' }}
              onChange={handleFileChange}
              disabled={isUploading}
            />
            {selectedFile ? (
              <div className="dropzone-file-info">
                <span className="file-icon">📄</span>
                <div className="file-details">
                  <span className="file-name">{selectedFile.name}</span>
                  <span className="file-size">
                    {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB · Ready to parse
                  </span>
                </div>
                <button
                  type="button"
                  className="file-remove-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = '';
                  }}
                >
                  ✕ Remove
                </button>
              </div>
            ) : (
              <div className="dropzone-prompt">
                <span className="upload-cloud-icon">☁️</span>
                <strong>Click to select or drag & drop textbook PDF</strong>
                <span>Supports digital PDF textbooks up to 50 MB</span>
              </div>
            )}
          </div>

          {/* Metadata Fields Grid */}
          <div className="upload-fields-grid">
            {/* Grade Selector */}
            <div className="upload-field-group">
              <label>Target Class / Grade</label>
              <select
                value={grade}
                onChange={(e) => setGrade(Number(e.target.value))}
                disabled={isUploading}
                className="upload-select"
              >
                {[5, 6, 7, 8, 9, 10, 11, 12].map((g) => (
                  <option key={g} value={g}>
                    Class {g} {g === 10 ? '(Board Exam)' : g === 5 ? '(Primary)' : ''}
                  </option>
                ))}
              </select>
            </div>

            {/* Subject Input */}
            <div className="upload-field-group">
              <label>Subject Name</label>
              <input
                type="text"
                placeholder="e.g. Physics, Chemistry, Math"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                disabled={isUploading}
                className="upload-input"
                required
              />
              <div className="subject-suggestions">
                {['Physics', 'Chemistry', 'Biology', 'Mathematics', 'History', 'Computer'].map((s) => (
                  <button
                    key={s}
                    type="button"
                    className="suggestion-chip"
                    onClick={() => setSubject(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Book Title Input */}
            <div className="upload-field-group">
              <label>Textbook Title</label>
              <input
                type="text"
                placeholder="e.g. Concepts of Physics - Vol 1"
                value={bookTitle}
                onChange={(e) => setBookTitle(e.target.value)}
                disabled={isUploading}
                className="upload-input"
                required
              />
            </div>

            {/* Chapter Details */}
            <div className="upload-field-group chapter-group">
              <div style={{ flex: '0 0 90px' }}>
                <label>Chapter #</label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={chapterNumber}
                  onChange={(e) => setChapterNumber(Number(e.target.value))}
                  disabled={isUploading}
                  className="upload-input"
                />
              </div>
              <div style={{ flex: 1 }}>
                <label>Chapter Title (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Electric Current and Circuits"
                  value={chapterTitle}
                  onChange={(e) => setChapterTitle(e.target.value)}
                  disabled={isUploading}
                  className="upload-input"
                />
              </div>
            </div>
          </div>

          {/* Ingestion Progress Indicator */}
          {isUploading && (
            <div className="ingestion-progress-box">
              <div className="progress-status-row">
                <span className="progress-spinner">⚙️</span>
                <span className="progress-step-text">
                  {uploadStep === 1 && '1/3: Validating PDF & Running Under-18 Content Safety Scan…'}
                  {uploadStep === 2 && '2/3: Parsing pages & splitting into semantic text chunks…'}
                  {uploadStep === 3 && '3/3: Embedding vectors & indexing into vector store…'}
                </span>
              </div>
              <div className="progress-bar-track">
                <div
                  className="progress-bar-fill"
                  style={{
                    width: uploadStep === 1 ? '33%' : uploadStep === 2 ? '66%' : '95%',
                  }}
                />
              </div>
            </div>
          )}

          {/* Submit Button */}
          <div className="upload-actions-bar">
            <button
              type="submit"
              disabled={isUploading || !selectedFile}
              className="ingest-submit-btn"
            >
              {isUploading ? (
                <>
                  <span className="spinner-dot" />
                  <span>Processing & Ingesting…</span>
                </>
              ) : (
                <>
                  <span>⚡ Ingest into Vector Space</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Previously Uploaded Custom Textbooks */}
      <div className="uploaded-list-section">
        <div className="uploaded-list-header">
          <h4>Custom Uploaded Textbooks ({uploadedBooks.length})</h4>
          <span className="list-subtitle">Managed under parental supervision</span>
        </div>

        {isLoadingBooks ? (
          <p className="loading-note">Loading textbooks…</p>
        ) : uploadedBooks.length === 0 ? (
          <div className="empty-uploaded-box">
            <span>📚</span>
            <p>No custom textbooks uploaded yet. Upload a PDF above to expand your child's curriculum.</p>
          </div>
        ) : (
          <div className="uploaded-cards-grid">
            {uploadedBooks.map((b) => (
              <div key={b.code || b.id} className="uploaded-book-card">
                <div className="book-card-top">
                  <div className="book-badge-row">
                    <span className="badge-grade">Class {b.grade}</span>
                    <span className="badge-subj">{b.subject}</span>
                    <span className="badge-chunks">⚡ {b.chunks_count} chunks</span>
                  </div>
                  <button
                    type="button"
                    className="delete-book-btn"
                    onClick={() => handleDeleteBook(b.code || b.id)}
                    disabled={deletingCode === (b.code || b.id)}
                    title="Remove textbook from vector space"
                  >
                    {deletingCode === (b.code || b.id) ? '…' : '🗑️'}
                  </button>
                </div>

                <h5 className="book-title-text">{b.book_title}</h5>
                <p className="book-ch-text">Ch {b.chapter_number}: {b.chapter_title}</p>

                <div className="book-meta-footer">
                  <span>📄 {b.pages_count} pages ({b.file_size_kb} KB)</span>
                  <span className="upload-date">{b.uploaded_at}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

