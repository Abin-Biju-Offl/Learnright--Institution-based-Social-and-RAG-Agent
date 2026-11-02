import React, { useState, useEffect, useCallback } from 'react';

/**
 * FlaggedAlertsTab
 * Review list for blocked and flagged queries with category tags, severity badges,
 * student query text, refusal reasons, and review actions (acknowledge/dismiss with notes).
 */
export default function FlaggedAlertsTab({ token, onAlertCountChange }) {
  const [events, setEvents] = useState([]);
  const [unreviewedCount, setUnreviewedCount] = useState(0);
  const [statusFilter, setStatusFilter] = useState('PENDING'); // 'PENDING' | 'REVIEWED' | 'ALL'
  const [categoryFilter, setCategoryFilter] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [noteInputs, setNoteInputs] = useState({});
  const [submittingIds, setSubmittingIds] = useState(new Set());

  const fetchFlagged = useCallback(async () => {
    setIsLoading(true);
    setError('');

    const params = new URLSearchParams();
    params.set('status', statusFilter);
    if (categoryFilter) params.set('category', categoryFilter);

    try {
      const res = await fetch(`/api/parent/flagged?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.ok) {
        const data = await res.json();
        setEvents(data.events || []);
        setUnreviewedCount(data.unreviewed_count || 0);
        if (onAlertCountChange) {
          onAlertCountChange(data.unreviewed_count || 0);
        }
      } else if (res.status === 401) {
        setError('Session expired. Please re-authenticate.');
      } else {
        setError('Failed to fetch flagged alerts.');
      }
    } catch {
      setError('Network connection error.');
    } finally {
      setIsLoading(false);
    }
  }, [token, statusFilter, categoryFilter, onAlertCountChange]);

  useEffect(() => {
    fetchFlagged();
  }, [fetchFlagged]);

  // Handle reviewing a flag
  const handleReview = async (eventId) => {
    const notes = noteInputs[eventId] || '';
    setSubmittingIds((prev) => new Set(prev).add(eventId));

    try {
      const res = await fetch(`/api/parent/flagged/${eventId}/review`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          action: 'reviewed',
          notes,
        }),
      });

      if (res.ok) {
        const updated = await res.json();
        // Update local event in list
        setEvents((prev) =>
          prev.map((ev) =>
            ev.event_id === eventId
              ? {
                  ...ev,
                  parent_review_status: 'REVIEWED',
                  reviewed_at: updated.reviewed_at,
                  parent_notes: updated.parent_notes,
                }
              : ev
          )
        );
        // Decrement unreviewed counter
        setUnreviewedCount((prev) => {
          const next = Math.max(0, prev - 1);
          if (onAlertCountChange) onAlertCountChange(next);
          return next;
        });
      } else {
        alert('Failed to submit review.');
      }
    } catch {
      alert('Network error while submitting review.');
    } finally {
      setSubmittingIds((prev) => {
        const next = new Set(prev);
        next.delete(eventId);
        return next;
      });
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      {/* ── Filter Bar ── */}
      <div className="alerts-filter-bar">
        <div style={{ display: 'flex', gap: '8px' }}>
          {[
            { id: 'PENDING', label: `Pending Review (${unreviewedCount})` },
            { id: 'REVIEWED', label: 'Reviewed' },
            { id: 'ALL', label: 'All Alerts' },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`parental-tab ${statusFilter === tab.id ? 'active' : ''}`}
              style={{ background: statusFilter === tab.id ? 'rgba(66, 133, 244, 0.15)' : 'rgba(255, 255, 255, 0.04)' }}
              onClick={() => setStatusFilter(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <select
          className="history-select"
          style={{ marginLeft: 'auto' }}
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
        >
          <option value="">All Categories</option>
          <option value="adult_sexual">Adult & Sexual</option>
          <option value="violence_gore">Violence & Gore</option>
          <option value="self_harm">Self-Harm & Suicide</option>
          <option value="hate_speech">Hate Speech</option>
          <option value="illegal_acts_weapons_drugs">Illegal Acts & Weapons</option>
          <option value="cyberbullying">Cyberbullying</option>
          <option value="other_inappropriate">Other Inappropriate</option>
          <option value="custom_blocked">Custom Blocked Words</option>
        </select>
      </div>

      {error && (
        <div className="parental-alert-msg parental-alert-error">
          <span>⚠️</span> {error}
        </div>
      )}

      {/* ── Alerts List ── */}
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#8e918f' }}>
          Loading safety alerts and blocked queries…
        </div>
      ) : events.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#8e918f' }}>
          {statusFilter === 'PENDING'
            ? '✓ No unreviewed safety alerts. All clear!'
            : 'No alerts matching criteria found.'}
        </div>
      ) : (
        <div className="alerts-list">
          {events.map((ev) => {
            const isPending = (ev.parent_review_status || 'PENDING') === 'PENDING';
            const severityClass = (ev.severity || 'medium').toLowerCase();
            const formattedDate = new Date(ev.timestamp).toLocaleString();
            const isSubmitting = submittingIds.has(ev.event_id);

            return (
              <div
                key={ev.event_id}
                className={`alert-card ${severityClass}`}
              >
                {/* Header with Severity & Category */}
                <div className="alert-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className={`severity-badge ${severityClass}`}>
                      {ev.severity || 'ALERT'}
                    </span>
                    <span className="badge-grade">
                      {(ev.category || 'Inappropriate Content').replace(/_/g, ' ').toUpperCase()}
                    </span>
                    <span className="badge-subject">Class {ev.student_grade} · {ev.subject}</span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#8e918f' }}>
                    {formattedDate}
                  </div>
                </div>

                {/* Exact Student Query */}
                <div>
                  <div style={{ fontSize: '11px', color: '#8e918f', marginBottom: '4px', fontWeight: 600 }}>
                    BLOCKED STUDENT QUERY:
                  </div>
                  <div className="query-quote-box">
                    "{ev.query_text}"
                  </div>
                </div>

                {/* Reason & Refusal Response */}
                <div>
                  <div style={{ fontSize: '11px', color: '#8e918f', marginBottom: '4px', fontWeight: 600 }}>
                    REFUSAL RESPONSE GIVEN TO STUDENT:
                  </div>
                  <div className="refusal-explanation-box">
                    {ev.refusal_response || 'This inquiry was refused per safety rules.'}
                  </div>
                </div>

                {/* Crisis helpline banner if self-harm */}
                {ev.category === 'self_harm' && (
                  <div
                    style={{
                      background: 'rgba(234, 67, 53, 0.1)',
                      border: '1px solid rgba(234, 67, 53, 0.3)',
                      borderRadius: '10px',
                      padding: '10px 14px',
                      fontSize: '12px',
                      color: '#f28b82',
                    }}
                  >
                    🚨 <strong>Crisis Alert:</strong> Please contact Tele-MANAS at <strong>14416</strong> or CHILDLINE at <strong>1098</strong> for immediate professional support.
                  </div>
                )}

                {/* Review Panel */}
                {isPending ? (
                  <div className="alert-review-panel">
                    <textarea
                      className="alert-notes-textarea"
                      placeholder="Add parent notes (e.g. Spoke with student about this question)…"
                      value={noteInputs[ev.event_id] || ''}
                      onChange={(e) =>
                        setNoteInputs({ ...noteInputs, [ev.event_id]: e.target.value })
                      }
                    />
                    <button
                      type="button"
                      className="review-btn-action"
                      onClick={() => handleReview(ev.event_id)}
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? 'Saving…' : '✓ Mark as Reviewed'}
                    </button>
                  </div>
                ) : (
                  <div className="reviewed-stamp">
                    <span>✓ Reviewed on {ev.reviewed_at ? new Date(ev.reviewed_at).toLocaleString() : 'recently'}</span>
                    {ev.parent_notes && (
                      <span style={{ color: '#c4c7c5' }}>— Notes: "{ev.parent_notes}"</span>
                    )}
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
