import React, { useState, useEffect, useCallback } from 'react';
import './institution.css';

export default function JoinInstitutionModal({
  isOpen,
  onClose,
  token,
  initialInviteToken = '',
  onJoinedSuccess,
}) {
  const [inviteInput, setInviteInput] = useState(initialInviteToken);
  const [verifyData, setVerifyData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const handleVerify = useCallback(async (codeToVerify) => {
    const clean = (codeToVerify || '').trim();
    if (!clean) return;
    setIsLoading(true);
    setErrorMsg('');
    setVerifyData(null);
    try {
      const res = await fetch(`/api/invites/${clean}/verify`);
      if (res.ok) {
        const data = await res.json();
        setVerifyData(data);
      } else {
        // Try as demo verification id for org joining
        setErrorMsg('Invalid or expired invite link. Please check the code.');
      }
    } catch {
      setErrorMsg('Network error verifying invite link.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      setErrorMsg('');
      setSuccessMsg('');
      setVerifyData(null);
      if (initialInviteToken) {
        setInviteInput(initialInviteToken);
        handleVerify(initialInviteToken);
      }
    }
  }, [isOpen, initialInviteToken, handleVerify]);

  const handleAcceptInvite = async () => {
    if (!token) {
      setErrorMsg('Please sign in first before accepting an invite link.');
      return;
    }
    const cleanToken = inviteInput.trim();
    setIsLoading(true);
    setErrorMsg('');
    try {
      const res = await fetch('/api/invites/accept', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ invite_token: cleanToken }),
      });
      if (res.ok) {
        const data = await res.json();
        setSuccessMsg(data.message || 'Successfully joined institution!');
        setTimeout(() => {
          if (onJoinedSuccess) onJoinedSuccess(data.tokens, data.user);
          onClose();
        }, 1200);
      } else {
        const d = await res.json();
        setErrorMsg(d.detail || 'Failed to accept invite.');
      }
    } catch {
      setErrorMsg('Network connection error.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="inst-modal-overlay" onClick={onClose}>
      <div className="inst-modal-card small" onClick={(e) => e.stopPropagation()}>
        <div className="inst-modal-header">
          <div className="inst-modal-header-left">
            <h3 className="inst-modal-title">
              <span>🏫</span>
              <span>Join Your Institution</span>
            </h3>
          </div>
          <button type="button" className="inst-close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="inst-body" style={{ padding: '24px' }}>
          <p style={{ color: '#9aa0a6', fontSize: 14, margin: '0 0 18px 0', lineHeight: 1.5 }}>
            Paste the invite link or 32-character code provided by your School Principal or Class Advisor.
          </p>

          {errorMsg && <div style={{ color: '#f28b82', fontSize: 13, marginBottom: 14 }}>⚠️ {errorMsg}</div>}
          {successMsg && <div style={{ color: '#81c995', fontSize: 13, marginBottom: 14 }}>✓ {successMsg}</div>}

          <div style={{ display: 'flex', gap: 10, marginBottom: 18 }}>
            <input
              type="text"
              className="inst-input"
              style={{ flex: 1 }}
              placeholder="Paste invite code or token..."
              value={inviteInput}
              onChange={(e) => setInviteInput(e.target.value)}
            />
            <button
              type="button"
              className="inst-btn inst-btn-secondary"
              onClick={() => handleVerify(inviteInput)}
              disabled={isLoading || !inviteInput.trim()}
            >
              Verify
            </button>
          </div>

          {verifyData && (
            <div style={{
              background: 'rgba(138, 180, 248, 0.08)',
              border: '1px solid rgba(138, 180, 248, 0.25)',
              borderRadius: 14,
              padding: 16,
              marginBottom: 20
            }}>
              <div style={{ fontSize: 12, color: '#8ab4f8', fontWeight: 600, marginBottom: 6 }}>
                INVITATION DETAILS
              </div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#ffffff', marginBottom: 6 }}>
                🏛️ {verifyData.institution_name}
              </div>
              <div style={{ fontSize: 13, color: '#e3e3e3', marginBottom: 4 }}>
                Role: <strong>{verifyData.target_role === 'student' ? 'Student' : 'Lecturer / Faculty'}</strong>
              </div>
              {verifyData.target_role === 'student' && (
                <div style={{ fontSize: 13, color: '#e3e3e3' }}>
                  Enrolling in: <strong>{verifyData.class_display_name || `Class ${verifyData.grade}`} (Section {verifyData.section_name})</strong>
                </div>
              )}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 10 }}>
            <button type="button" className="inst-btn inst-btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              type="button"
              className="inst-btn inst-btn-primary"
              onClick={handleAcceptInvite}
              disabled={isLoading || !inviteInput.trim()}
            >
              {isLoading ? 'Joining...' : 'Confirm & Join'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
