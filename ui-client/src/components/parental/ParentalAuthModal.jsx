import React, { useState, useEffect, useCallback, useRef } from 'react';
import { ShieldIcon } from './ParentalNavButton';
import './parental.css';

/**
 * Padlock SVG Icon
 */
function LockIcon({ size = 20, color = 'currentColor' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

/**
 * ParentalAuthModal
 * Handles parental authentication, setup, progressive lockout timer,
 * shake animation on error, and recovery key resets.
 */
export default function ParentalAuthModal({ isOpen, onClose, onSuccess }) {
  // Modal view modes: 'verify' | 'setup' | 'reset' | 'recovery_saved'
  const [viewMode, setViewMode] = useState('verify');
  const [pinDigits, setPinDigits] = useState('');
  const [isShaking, setIsShaking] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Lockout state
  const [isLocked, setIsLocked] = useState(false);
  const [lockoutSeconds, setLockoutSeconds] = useState(0);

  // Setup form state
  const [setupPin, setSetupPin] = useState('');
  const [setupConfirm, setSetupConfirm] = useState('');
  const [issuedRecoveryKey, setIssuedRecoveryKey] = useState('');
  const [pendingToken, setPendingToken] = useState(null);

  // Reset form state
  const [recoveryKeyInput, setRecoveryKeyInput] = useState('');
  const [newPinInput, setNewPinInput] = useState('');
  const [confirmNewPinInput, setConfirmNewPinInput] = useState('');

  // Timer interval ref
  const timerRef = useRef(null);

  // Fetch authentication status
  const checkAuthStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/parent/auth/status');
      if (res.ok) {
        const data = await res.json();
        if (!data.pin_configured) {
          setViewMode('setup');
        } else {
          setViewMode('verify');
        }

        if (data.is_locked && data.lockout_remaining_seconds > 0) {
          setIsLocked(true);
          setLockoutSeconds(data.lockout_remaining_seconds);
        } else {
          setIsLocked(false);
          setLockoutSeconds(0);
        }
      } else {
        setErrorMessage('Cannot reach backend server. Please verify FastAPI is running on port 8000.');
      }
    } catch (err) {
      console.error('Failed to fetch parental auth status', err);
      setErrorMessage('Cannot connect to backend server. Please verify FastAPI is running on port 8000.');
    }
  }, []);

  // Check status on open
  useEffect(() => {
    if (isOpen) {
      setPinDigits('');
      setErrorMessage('');
      setSuccessMessage('');
      checkAuthStatus();
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isOpen, checkAuthStatus]);

  // Lockout countdown timer
  useEffect(() => {
    if (isLocked && lockoutSeconds > 0) {
      timerRef.current = setInterval(() => {
        setLockoutSeconds((prev) => {
          if (prev <= 1) {
            clearInterval(timerRef.current);
            setIsLocked(false);
            setErrorMessage('');
            checkAuthStatus();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isLocked, lockoutSeconds, checkAuthStatus]);

  // Format seconds to mm:ss
  const formatTime = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // Submit PIN for verification
  const handleVerifyPin = useCallback(
    async (pin) => {
      if (!pin || pin.length < 4) return;
      setIsLoading(true);
      setErrorMessage('');

      try {
        const res = await fetch('/api/parent/auth/verify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pin }),
        });

        if (res.ok) {
          const data = await res.json();
          setPinDigits('');
          if (onSuccess) {
            onSuccess(data.token, data.expires_in_seconds);
          }
        } else if (res.status === 429) {
          const data = await res.json();
          setIsLocked(true);
          setLockoutSeconds(data.lockout_remaining_seconds || 300);
          setErrorMessage(data.detail || 'Portal locked due to multiple failed attempts.');
          setPinDigits('');
        } else {
          const data = await res.json();
          setErrorMessage(data.detail || 'Incorrect PIN. Please try again.');
          setIsShaking(true);
          setTimeout(() => {
            setIsShaking(false);
            setPinDigits('');
          }, 450);
        }
      } catch (err) {
        setErrorMessage('Could not connect to server. Check connection.');
      } finally {
        setIsLoading(false);
      }
    },
    [onSuccess]
  );

  // Keypad clicks
  const handleKeypadPress = (val) => {
    if (isLocked || isLoading) return;

    if (val === 'clear') {
      setPinDigits('');
      setErrorMessage('');
    } else if (val === 'back') {
      setPinDigits((prev) => prev.slice(0, -1));
      setErrorMessage('');
    } else {
      if (pinDigits.length >= 6) return;
      const next = pinDigits + val;
      setPinDigits(next);
      setErrorMessage('');

      // Auto submit on 4 digits
      if (next.length === 4) {
        handleVerifyPin(next);
      }
    }
  };

  // Physical keyboard support
  useEffect(() => {
    if (!isOpen || viewMode !== 'verify' || isLocked) return;

    const handleKeyDown = (e) => {
      if (e.key >= '0' && e.key <= '9') {
        handleKeypadPress(e.key);
      } else if (e.key === 'Backspace') {
        handleKeypadPress('back');
      } else if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, viewMode, isLocked, pinDigits, handleVerifyPin, onClose]);

  // Handle Initial PIN Setup
  const handleSetupSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');

    if (setupPin.length < 4 || setupPin.length > 6) {
      setErrorMessage('PIN must be 4 to 6 numeric digits.');
      return;
    }
    if (setupPin !== setupConfirm) {
      setErrorMessage('PIN confirmation does not match.');
      return;
    }

    setIsLoading(true);
    try {
      const res = await fetch('/api/parent/auth/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: setupPin, confirm_pin: setupConfirm }),
      });

      if (res.ok) {
        const data = await res.json();
        setIssuedRecoveryKey(data.recovery_key);
        setPendingToken(data.token);
        setViewMode('recovery_saved');
      } else {
        const data = await res.json();
        setErrorMessage(data.detail || 'Setup failed. Please try again.');
      }
    } catch {
      setErrorMessage('Setup failed. Network error.');
    } finally {
      setIsLoading(false);
    }
  };

  // Complete Setup after saving recovery key
  const handleProceedAfterSetup = () => {
    if (pendingToken && onSuccess) {
      onSuccess(pendingToken, 900);
    }
  };

  // Handle Emergency Recovery Key Reset
  const handleResetSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');

    if (!recoveryKeyInput.trim()) {
      setErrorMessage('Please enter your 16-character Recovery Key.');
      return;
    }
    if (newPinInput.length < 4 || newPinInput.length > 6) {
      setErrorMessage('New PIN must be 4 to 6 digits.');
      return;
    }
    if (newPinInput !== confirmNewPinInput) {
      setErrorMessage('PIN confirmation does not match.');
      return;
    }

    setIsLoading(true);
    try {
      const res = await fetch('/api/parent/auth/reset-pin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recovery_key: recoveryKeyInput.trim(),
          new_pin: newPinInput,
          confirm_new_pin: confirmNewPinInput,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setSuccessMessage('PIN successfully reset!');
        setTimeout(() => {
          if (onSuccess) {
            onSuccess(data.token, data.expires_in_seconds);
          }
        }, 800);
      } else {
        const data = await res.json();
        setErrorMessage(data.detail || 'Recovery key invalid or PIN reset failed.');
      }
    } catch {
      setErrorMessage('Reset failed due to connection error.');
    } finally {
      setIsLoading(false);
    }
  };

  // Copy recovery key to clipboard
  const handleCopyRecoveryKey = () => {
    if (issuedRecoveryKey) {
      navigator.clipboard.writeText(issuedRecoveryKey);
      setSuccessMessage('Recovery Key copied to clipboard!');
      setTimeout(() => setSuccessMessage(''), 2500);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="parental-modal-overlay" onClick={onClose}>
      <div
        className={`parental-auth-card ${isShaking ? 'pin-shake' : ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          className="parental-auth-close"
          onClick={onClose}
          aria-label="Close"
        >
          ✕
        </button>

        {/* Top Shield / Lock Icon */}
        <div className="parental-auth-shield-wrap">
          {isLocked ? <LockIcon size={26} color="#f28b82" /> : <ShieldIcon size={28} color="#8ab4f8" />}
        </div>

        {/* ── MODE 1: VERIFY PIN (NORMAL LOGIN) ── */}
        {viewMode === 'verify' && !isLocked && (
          <>
            <h3 className="parental-auth-title">Parental Verification</h3>
            <p className="parental-auth-subtitle">
              Enter your parental PIN to view student chat history and configure safety filters.
            </p>

            {errorMessage && (
              <div className="parental-alert-msg parental-alert-error">
                <span>⚠️</span> {errorMessage}
              </div>
            )}

            {/* PIN Dots (4 standard dots) */}
            <div className="pin-dots-container">
              {[0, 1, 2, 3].map((idx) => {
                const filled = pinDigits.length > idx;
                const isError = Boolean(errorMessage);
                return (
                  <div
                    key={idx}
                    className={`pin-dot ${filled ? 'filled' : ''} ${isError && filled ? 'error' : ''}`}
                  />
                );
              })}
            </div>

            {/* Numeric Keypad */}
            <div className="pin-keypad">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((num) => (
                <button
                  key={num}
                  type="button"
                  className="pin-key"
                  onClick={() => handleKeypadPress(num.toString())}
                  disabled={isLoading}
                >
                  {num}
                </button>
              ))}
              <button
                type="button"
                className="pin-key action-key"
                onClick={() => handleKeypadPress('clear')}
                disabled={isLoading}
              >
                Clear
              </button>
              <button
                type="button"
                className="pin-key"
                onClick={() => handleKeypadPress('0')}
                disabled={isLoading}
              >
                0
              </button>
              <button
                type="button"
                className="pin-key action-key"
                onClick={() => handleKeypadPress('back')}
                disabled={isLoading}
                aria-label="Backspace"
              >
                ⌫
              </button>
            </div>

            <button
              type="button"
              className="parental-auth-switch"
              onClick={() => {
                setErrorMessage('');
                setViewMode('reset');
              }}
            >
              Forgot PIN? Reset with Recovery Key
            </button>
          </>
        )}

        {/* ── MODE 2: BRUTE FORCE LOCKOUT ── */}
        {isLocked && (
          <div className="lockout-card">
            <h3 className="parental-auth-title" style={{ color: '#f28b82' }}>
              Portal Security Lockout
            </h3>
            <p className="parental-auth-subtitle">
              Repeated incorrect PIN attempts detected. For student safety, access is temporarily suspended.
            </p>
            <div className="lockout-timer">{formatTime(lockoutSeconds)}</div>
            <p style={{ fontSize: '12px', color: '#8e918f', margin: 0 }}>
              The keypad will automatically re-enable when the timer completes.
            </p>
          </div>
        )}

        {/* ── MODE 3: FIRST-TIME SETUP ── */}
        {viewMode === 'setup' && (
          <form onSubmit={handleSetupSubmit} style={{ width: '100%' }}>
            <h3 className="parental-auth-title">Set Parental PIN</h3>
            <p className="parental-auth-subtitle">
              Create a 4 to 6-digit numeric PIN to monitor student conversations and configure content safety filters.
            </p>

            {errorMessage && (
              <div className="parental-alert-msg parental-alert-error">
                <span>⚠️</span> {errorMessage}
              </div>
            )}

            <div className="parental-form-group">
              <label className="parental-form-label">Create 4-Digit PIN</label>
              <input
                type="password"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                className="parental-input"
                placeholder="e.g. 2468"
                value={setupPin}
                onChange={(e) => setSetupPin(e.target.value.replace(/\D/g, ''))}
                required
                autoFocus
              />
            </div>

            <div className="parental-form-group">
              <label className="parental-form-label">Confirm PIN</label>
              <input
                type="password"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                className="parental-input"
                placeholder="Re-enter your PIN"
                value={setupConfirm}
                onChange={(e) => setSetupConfirm(e.target.value.replace(/\D/g, ''))}
                required
              />
            </div>

            <button
              type="submit"
              className="parental-action-btn"
              disabled={isLoading || setupPin.length < 4 || setupPin !== setupConfirm}
            >
              {isLoading ? 'Configuring…' : 'Save PIN & Continue'}
            </button>
          </form>
        )}

        {/* ── MODE 4: RECOVERY KEY DISPLAY (POST-SETUP) ── */}
        {viewMode === 'recovery_saved' && (
          <div style={{ width: '100%' }}>
            <h3 className="parental-auth-title">Emergency Recovery Key</h3>
            <p className="parental-auth-subtitle">
              Save this 16-character recovery key in a safe place. You can use it to reset your PIN if you forget it.
            </p>

            {successMessage && (
              <div className="parental-alert-msg parental-alert-success">
                <span>✓</span> {successMessage}
              </div>
            )}

            <div className="recovery-key-display">
              <span>{issuedRecoveryKey}</span>
              <button
                type="button"
                className="history-btn-secondary"
                onClick={handleCopyRecoveryKey}
                style={{ marginLeft: '8px' }}
              >
                Copy
              </button>
            </div>

            <p style={{ fontSize: '11px', color: '#8e918f', marginBottom: '16px' }}>
              🔒 This key will only be shown once. Please save it securely.
            </p>

            <button
              type="button"
              className="parental-action-btn"
              onClick={handleProceedAfterSetup}
            >
              Open Parental Control Center →
            </button>
          </div>
        )}

        {/* ── MODE 5: RESET PIN VIA RECOVERY KEY ── */}
        {viewMode === 'reset' && (
          <form onSubmit={handleResetSubmit} style={{ width: '100%' }}>
            <h3 className="parental-auth-title">Reset Forgotten PIN</h3>
            <p className="parental-auth-subtitle">
              Enter your emergency recovery key to create a new parental PIN.
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

            <div className="parental-form-group">
              <label className="parental-form-label">Emergency Recovery Key</label>
              <input
                type="text"
                className="parental-input"
                placeholder="e.g. NCERT-XXXX-XXXX-XXXX"
                value={recoveryKeyInput}
                onChange={(e) => setRecoveryKeyInput(e.target.value.toUpperCase())}
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
                value={newPinInput}
                onChange={(e) => setNewPinInput(e.target.value.replace(/\D/g, ''))}
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
                value={confirmNewPinInput}
                onChange={(e) => setConfirmNewPinInput(e.target.value.replace(/\D/g, ''))}
                required
              />
            </div>

            <button
              type="submit"
              className="parental-action-btn"
              disabled={isLoading || !recoveryKeyInput.trim() || newPinInput.length < 4}
            >
              {isLoading ? 'Resetting…' : 'Reset PIN & Log In'}
            </button>

            <button
              type="button"
              className="parental-auth-switch"
              onClick={() => {
                setErrorMessage('');
                setViewMode('verify');
              }}
            >
              ← Back to PIN Keypad
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
