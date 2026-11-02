import React, { useState } from 'react';

/**
 * SecurityPinTab
 * Change PIN form, session token timer, and emergency recovery key generator/viewer.
 */
export default function SecurityPinTab({ token, onLogout, sessionExpiresIn = 900 }) {
  const [currentPin, setCurrentPin] = useState('');
  const [newPin, setNewPin] = useState('');
  const [confirmNewPin, setConfirmNewPin] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Handle PIN change
  const handleChangePin = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');

    if (newPin.length < 4 || newPin.length > 6) {
      setErrorMessage('New PIN must be 4 to 6 numeric digits.');
      return;
    }
    if (newPin !== confirmNewPin) {
      setErrorMessage('New PIN confirmation does not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await fetch('/api/parent/auth/change-pin', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_pin: currentPin,
          new_pin: newPin,
          confirm_new_pin: confirmNewPin,
        }),
      });

      if (res.ok) {
        setSuccessMessage('Parental PIN successfully updated!');
        setCurrentPin('');
        setNewPin('');
        setConfirmNewPin('');
      } else {
        const data = await res.json();
        setErrorMessage(data.detail || 'Failed to change PIN.');
      }
    } catch {
      setErrorMessage('Network error while changing PIN.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* ── Change PIN Section ── */}
      <div className="security-section">
        <h4 className="security-section-title">Change Parental PIN</h4>
        <p className="security-section-desc">
          Update your 4 to 6-digit numeric PIN used to unlock student chat history and filtering preferences.
        </p>

        {errorMessage && (
          <div className="parental-alert-msg parental-alert-error">
            <span>⚠️</span> {errorMessage}
          </div>
        )}
        {successMessage && (
          <div className="parental-alert-msg parental-alert-success">
            <span>✓</span> {successMessage}
          </div>
        )}

        <form onSubmit={handleChangePin} style={{ maxWidth: '420px' }}>
          <div className="parental-form-group">
            <label className="parental-form-label">Current PIN</label>
            <input
              type="password"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              className="parental-input"
              placeholder="Enter current PIN"
              value={currentPin}
              onChange={(e) => setCurrentPin(e.target.value.replace(/\D/g, ''))}
              required
            />
          </div>

          <div className="parental-form-group">
            <label className="parental-form-label">New PIN (4-6 Digits)</label>
            <input
              type="password"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              className="parental-input"
              placeholder="Enter new PIN"
              value={newPin}
              onChange={(e) => setNewPin(e.target.value.replace(/\D/g, ''))}
              required
            />
          </div>

          <div className="parental-form-group">
            <label className="parental-form-label">Confirm New PIN</label>
            <input
              type="password"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              className="parental-input"
              placeholder="Re-enter new PIN"
              value={confirmNewPin}
              onChange={(e) => setConfirmNewPin(e.target.value.replace(/\D/g, ''))}
              required
            />
          </div>

          <button
            type="submit"
            className="parental-action-btn"
            style={{ width: 'auto', padding: '10px 24px', marginTop: '6px' }}
            disabled={isSubmitting || !currentPin || newPin.length < 4}
          >
            {isSubmitting ? 'Updating…' : 'Update PIN'}
          </button>
        </form>
      </div>

      {/* ── Active Session Security ── */}
      <div className="security-section">
        <h4 className="security-section-title">Active Session & In-Memory Tokens</h4>
        <p className="security-section-desc">
          For student privacy and security, parental authentication uses an in-memory 256-bit cryptographic bearer token that expires automatically after 15 minutes of inactivity or when the browser tab is closed.
        </p>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ fontSize: '13px', color: '#c4c7c5' }}>
            🔒 Inactivity Auto-Lock: <strong style={{ color: '#8ab4f8' }}>15 minutes</strong>
          </div>
          <button
            type="button"
            className="lock-signout-btn"
            onClick={onLogout}
          >
            <span>🔒</span> Lock Portal & Sign Out Now
          </button>
        </div>
      </div>

      {/* ── Emergency Recovery Key Notice ── */}
      <div className="security-section">
        <h4 className="security-section-title">Emergency PIN Recovery</h4>
        <p className="security-section-desc">
          If you ever forget your parental PIN, click <em>"Forgot PIN?"</em> on the lock screen and enter the 16-character Emergency Recovery Key generated during initial setup.
        </p>
        <div style={{ fontSize: '12px', color: '#8e918f' }}>
          💡 If you lose both your PIN and Recovery Key, please consult the system administrator or check server storage logs.
        </div>
      </div>
    </div>
  );
}
