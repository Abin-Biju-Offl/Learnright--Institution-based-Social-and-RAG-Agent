import React, { useState, useEffect, useCallback } from 'react';

/**
 * ChatHistoryTab
 * Searchable, filterable student chat history viewer with conversation transcript view,
 * citation tags, safety status badges, export action, and purge capabilities.
 */
export default function ChatHistoryTab({ token }) {
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Filters
  const [search, setSearch] = useState('');
  const [grade, setGrade] = useState('');
  const [subject, setSubject] = useState('');
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [limit] = useState(25);
  const [offset, setOffset] = useState(0);

  const fetchHistory = useCallback(async () => {
    setIsLoading(true);
    setError('');

    const params = new URLSearchParams();
    params.set('limit', limit.toString());
    params.set('offset', offset.toString());
    if (search.trim()) params.set('search', search.trim());
    if (grade) params.set('grade', grade);
    if (subject) params.set('subject', subject);
    if (flaggedOnly) params.set('flagged_only', 'true');

    try {
      const res = await fetch(`/api/parent/history?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.ok) {
        const data = await res.json();
        setRecords(data.records || []);
        setTotal(data.total || 0);
      } else if (res.status === 401) {
        setError('Session expired. Please re-authenticate.');
      } else {
        setError('Failed to fetch conversation history.');
      }
    } catch {
      setError('Network connection error.');
    } finally {
      setIsLoading(false);
    }
  }, [token, limit, offset, search, grade, subject, flaggedOnly]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // Handle export
  const handleExport = () => {
    if (records.length === 0) return;
    const blob = new Blob([JSON.stringify(records, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ncert_student_chat_history_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Handle clear history
  const handleClear = async () => {
    if (!window.confirm('Are you sure you want to permanently clear the server-side chat history?')) {
      return;
    }

    try {
      const res = await fetch('/api/parent/history', {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.ok) {
        setRecords([]);
        setTotal(0);
        setOffset(0);
      } else {
        alert('Failed to clear history on server.');
      }
    } catch {
      alert('Network error while clearing history.');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* ── Filter Controls ── */}
      <div className="history-controls">
        <input
          type="text"
          className="history-search-input"
          placeholder="Search questions and answers…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
        />

        <select
          className="history-select"
          value={grade}
          onChange={(e) => {
            setGrade(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All Classes</option>
          <option value="5">Class 5</option>
          <option value="10">Class 10</option>
        </select>

        <select
          className="history-select"
          value={subject}
          onChange={(e) => {
            setSubject(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All Subjects</option>
          <option value="Science">Science</option>
          <option value="English">English</option>
          <option value="Social Science">Social Science</option>
        </select>

        <select
          className="history-select"
          value={flaggedOnly ? 'flagged' : 'all'}
          onChange={(e) => {
            setFlaggedOnly(e.target.value === 'flagged');
            setOffset(0);
          }}
        >
          <option value="all">All Status</option>
          <option value="flagged">🚨 Flagged Only</option>
        </select>

        <button
          type="button"
          className="history-btn-secondary"
          onClick={handleExport}
          title="Download chat transcripts as JSON"
          disabled={records.length === 0}
        >
          <span>📥</span> Export JSON
        </button>

        <button
          type="button"
          className="history-btn-secondary"
          onClick={handleClear}
          title="Clear all saved history"
          style={{ color: '#f28b82' }}
          disabled={total === 0}
        >
          <span>🗑️</span> Clear All
        </button>
      </div>

      {error && (
        <div className="parental-alert-msg parental-alert-error">
          <span>⚠️</span> {error}
        </div>
      )}

      {/* ── Record Count Summary ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', color: '#8e918f' }}>
        <span>
          Showing {records.length} of {total} student conversation{total === 1 ? '' : 's'}
        </span>
        {total > limit && (
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              className="history-btn-secondary"
              disabled={offset === 0}
              onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
            >
              ← Prev
            </button>
            <button
              type="button"
              className="history-btn-secondary"
              disabled={offset + limit >= total}
              onClick={() => setOffset((prev) => prev + limit)}
            >
              Next →
            </button>
          </div>
        )}
      </div>

      {/* ── Conversation Records List ── */}
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#8e918f' }}>
          Loading student conversation records…
        </div>
      ) : records.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#8e918f' }}>
          No conversation history matching criteria found.
        </div>
      ) : (
        <div className="history-records-list">
          {records.map((rec) => {
            const isFlagged = rec.flagged || rec.safety_status !== 'CLEAN';
            const formattedDate = new Date(rec.timestamp).toLocaleString();

            return (
              <div
                key={rec.turn_id}
                className={`history-turn-card ${isFlagged ? 'flagged' : ''}`}
              >
                {/* Meta Header */}
                <div className="turn-header">
                  <div className="turn-meta-pills">
                    <span className="badge-grade">Class {rec.student_grade}</span>
                    <span className="badge-subject">{rec.subject}</span>
                    {rec.chapter && (
                      <span className="badge-subject">Ch {rec.chapter}</span>
                    )}
                    {isFlagged ? (
                      <span className="badge-flagged-pill">
                        🚨 {rec.safety_category ? rec.safety_category.toUpperCase() : 'FLAGGED'}
                      </span>
                    ) : (
                      <span className="badge-clean-pill">✓ Clean</span>
                    )}
                    {rec.pure_llm && (
                      <span style={{ fontSize: '11px', color: '#fdd663' }}>✨ Pure AI</span>
                    )}
                  </div>
                  <span>{formattedDate}</span>
                </div>

                {/* Student Query */}
                <div className="turn-student-bubble">
                  <strong style={{ color: '#8ab4f8' }}>Student:</strong> {rec.question}
                </div>

                {/* Assistant Answer */}
                <div className="turn-answer-bubble">
                  <div style={{ fontWeight: 600, color: '#e3e3e3', marginBottom: '4px' }}>
                    Tutor Response:
                  </div>
                  <div>{rec.answer}</div>
                </div>

                {/* Citations (if present) */}
                {rec.sources && rec.sources.length > 0 && (
                  <div className="turn-sources-row">
                    <span style={{ color: '#8e918f' }}>📚 Citations:</span>
                    {rec.sources.map((src, sIdx) => (
                      <span key={sIdx} className="citation-chip">
                        Ch {src.chapter} · Pg {src.page}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
