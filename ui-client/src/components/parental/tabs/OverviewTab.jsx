import React, { useState, useEffect, useCallback } from 'react';

/**
 * OverviewTab
 * Displays high-level student activity and safety metrics, compliance rate,
 * top subjects studied, flagged category counts, and national crisis helpline banners.
 */
export default function OverviewTab({ token, onSwitchTab }) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchOverview = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const res = await fetch('/api/parent/overview', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.ok) {
        const overview = await res.json();
        setData(overview);
      } else if (res.status === 401) {
        setError('Session expired. Please re-authenticate.');
      } else {
        setError('Failed to load overview data.');
      }
    } catch {
      setError('Network connection error.');
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: '#8e918f' }}>
        <div style={{ fontSize: '24px', marginBottom: '8px' }}>🔄</div>
        Loading safety metrics and student activity…
      </div>
    );
  }

  if (error) {
    return (
      <div className="parental-alert-msg parental-alert-error" style={{ margin: '20px auto' }}>
        <span>⚠️</span> {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ textAlign: 'center', padding: '48px 24px', color: '#8e918f' }}>
        <div style={{ fontSize: '28px', marginBottom: '12px' }}>📊</div>
        <p style={{ margin: '0 0 16px 0', fontSize: '14px' }}>No activity metrics recorded yet.</p>
        <button
          type="button"
          onClick={fetchOverview}
          className="parental-preset-btn"
          style={{ padding: '8px 18px', background: 'rgba(138, 180, 248, 0.15)', color: '#8ab4f8' }}
        >
          🔄 Refresh Safety Metrics
        </button>
      </div>
    );
  }

  const compliancePercent = data.safety_compliance_rate_percent ?? 100;
  const hasUnreviewed = (data.unreviewed_alerts || 0) > 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* ── Key Metrics Grid ── */}
      <div className="overview-grid">
        <div className="overview-stat-card">
          <div className="overview-stat-header">
            <span>TOTAL STUDENT QUERIES</span>
            <span>📚</span>
          </div>
          <div className="overview-stat-val">{data.total_student_queries}</div>
          <div className="overview-stat-footer">
            {data.clean_queries} clean conversations logged
          </div>
        </div>

        <div className={`overview-stat-card ${hasUnreviewed ? 'overview-card-highlight' : ''}`}>
          <div className="overview-stat-header">
            <span>FLAGGED & BLOCKED</span>
            <span>🛡️</span>
          </div>
          <div className="overview-stat-val">{data.flagged_queries}</div>
          <div className="overview-stat-footer">
            {hasUnreviewed ? (
              <span style={{ color: '#f28b82', fontWeight: 600 }}>
                {data.unreviewed_alerts} unreviewed alert{data.unreviewed_alerts > 1 ? 's' : ''}
              </span>
            ) : (
              'All alerts reviewed'
            )}
          </div>
        </div>

        <div className="overview-stat-card">
          <div className="overview-stat-header">
            <span>SAFETY COMPLIANCE</span>
            <span>✓</span>
          </div>
          <div className="overview-stat-val" style={{ color: '#81c995' }}>
            {compliancePercent}%
          </div>
          <div className="overview-stat-footer">Safe educational inquiry rate</div>
        </div>

        <div className="overview-stat-card">
          <div className="overview-stat-header">
            <span>ACTIVE STUDY DAYS</span>
            <span>📅</span>
          </div>
          <div className="overview-stat-val">{data.active_days_count}</div>
          <div className="overview-stat-footer">Days with textbook interactions</div>
        </div>
      </div>

      {/* ── Compliance Bar Section ── */}
      <div className="compliance-container">
        <div className="compliance-header">
          <div>
            <div style={{ fontWeight: 600, fontSize: '14px', color: '#e3e3e3' }}>
              Textbook Learning Safety Index
            </div>
            <div style={{ fontSize: '12px', color: '#8e918f' }}>
              Ratio of safe, curriculum-aligned inquiries versus safety blocks
            </div>
          </div>
          <div style={{ fontSize: '16px', fontWeight: 700, color: '#81c995' }}>
            {compliancePercent}% Safe
          </div>
        </div>
        <div className="compliance-bar-track">
          <div
            className="compliance-bar-fill"
            style={{ width: `${Math.min(100, Math.max(0, compliancePercent))}%` }}
          />
        </div>
      </div>

      {/* ── Top Studied Subjects ── */}
      <div>
        <div style={{ fontSize: '14px', fontWeight: 600, color: '#e3e3e3', marginBottom: '10px' }}>
          Top Studied Subjects
        </div>
        <div className="subjects-breakdown-grid">
          {(data.top_studied_subjects || []).length > 0 ? (
            data.top_studied_subjects.map((item, idx) => (
              <div key={idx} className="subject-item-box">
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#e3e3e3' }}>
                    {item.subject}
                  </div>
                  <div style={{ fontSize: '11px', color: '#8e918f' }}>
                    Class {item.grade} NCERT
                  </div>
                </div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#8ab4f8' }}>
                  {item.queries} queries
                </div>
              </div>
            ))
          ) : (
            <div style={{ fontSize: '13px', color: '#8e918f' }}>
              No subject study logs recorded yet.
            </div>
          )}
        </div>
      </div>

      {/* ── Flagged Categories Breakdown (if any) ── */}
      {data.flagged_category_breakdown && (
        <div>
          <div style={{ fontSize: '14px', fontWeight: 600, color: '#e3e3e3', marginBottom: '10px' }}>
            Interception Summary by Safety Category
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {Object.entries(data.flagged_category_breakdown).map(([cat, count]) => (
              <div
                key={cat}
                style={{
                  background: count > 0 ? 'rgba(234, 67, 53, 0.12)' : 'rgba(255, 255, 255, 0.04)',
                  border: `1px solid ${count > 0 ? 'rgba(234, 67, 53, 0.3)' : 'rgba(255, 255, 255, 0.08)'}`,
                  color: count > 0 ? '#f28b82' : '#8e918f',
                  padding: '6px 12px',
                  borderRadius: '10px',
                  fontSize: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <span style={{ textTransform: 'capitalize' }}>
                  {cat.replace(/_/g, ' ')}
                </span>
                <span style={{ fontWeight: 700 }}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── National Emergency Crisis Helplines ── */}
      <div className="helplines-card">
        <div className="helplines-title">
          <span>🇮🇳</span> National Child Safety & Emergency Crisis Helplines (India)
        </div>
        <div className="helpline-tags-row">
          <div className="helpline-chip" title="National Mental Health Helpline (24x7 Toll-Free)">
            <span>Tele-MANAS:</span>
            <span className="helpline-number">14416</span>
          </div>
          <div className="helpline-chip" title="National Child Helpline (Govt of India, 24x7)">
            <span>CHILDLINE:</span>
            <span className="helpline-number">1098</span>
          </div>
          <div className="helpline-chip" title="Mental Health Rehabilitation Helpline">
            <span>KIRAN:</span>
            <span className="helpline-number">1800-599-0019</span>
          </div>
        </div>
      </div>
    </div>
  );
}
