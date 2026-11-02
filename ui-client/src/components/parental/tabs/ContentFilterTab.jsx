import React, { useState, useEffect, useCallback } from 'react';

/**
 * ContentFilterTab
 * Configurable category toggles, strictness presets (Strict Elementary vs Curriculum Standard),
 * custom blocked keyword manager (add/remove custom words), and explanation of NCERT Biology preservation.
 */
export default function ContentFilterTab({ token }) {
  const [settings, setSettings] = useState(null);
  const [profile, setProfile] = useState('curriculum_standard');
  const [categories, setCategories] = useState({
    adult_sexual: true,
    violence_gore: true,
    self_harm: true,
    hate_speech: true,
    illegal_acts_weapons_drugs: true,
    cyberbullying: true,
    other_inappropriate: true,
  });
  const [allowBiology, setAllowBiology] = useState(true);
  const [keywords, setKeywords] = useState([]);
  const [newKeyword, setNewKeyword] = useState('');
  const [timeoutMinutes, setTimeoutMinutes] = useState(15);

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState('');

  const fetchSettings = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const res = await fetch('/api/parent/settings', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.ok) {
        const data = await res.json();
        setSettings(data);
        setProfile(data.strictness_profile || 'curriculum_standard');
        setCategories(data.categories || {});
        setAllowBiology(data.allow_ncert_biology_reproduction ?? true);
        setKeywords(data.custom_blocked_keywords || []);
        setTimeoutMinutes(data.session_timeout_minutes || 15);
      } else if (res.status === 401) {
        setError('Session expired. Please re-authenticate.');
      } else {
        setError('Failed to load settings.');
      }
    } catch {
      setError('Network connection error.');
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  // Handle Preset Selection
  const handleSelectPreset = (selectedPreset) => {
    setProfile(selectedPreset);
    if (selectedPreset === 'strict_elementary') {
      setCategories({
        adult_sexual: true,
        violence_gore: true,
        self_harm: true,
        hate_speech: true,
        illegal_acts_weapons_drugs: true,
        cyberbullying: true,
        other_inappropriate: true,
      });
      setAllowBiology(false);
    } else if (selectedPreset === 'curriculum_standard') {
      setCategories({
        adult_sexual: true,
        violence_gore: true,
        self_harm: true,
        hate_speech: true,
        illegal_acts_weapons_drugs: true,
        cyberbullying: true,
        other_inappropriate: true,
      });
      setAllowBiology(true);
    }
  };

  // Toggle Category
  const handleToggleCategory = (key) => {
    if (key === 'self_harm' || key === 'illegal_acts_weapons_drugs') {
      return; // Inviolable locked categories
    }
    setProfile('custom');
    setCategories((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  // Add custom keyword
  const handleAddKeyword = (e) => {
    e.preventDefault();
    const clean = newKeyword.trim().toLowerCase();
    if (clean && !keywords.includes(clean)) {
      setKeywords([...keywords, clean]);
      setNewKeyword('');
    }
  };

  // Remove custom keyword
  const handleRemoveKeyword = (word) => {
    setKeywords(keywords.filter((k) => k !== word));
  };

  // Save Settings to Backend
  const handleSaveSettings = async () => {
    setIsSaving(true);
    setError('');
    setSaveSuccess(false);

    try {
      const payload = {
        strictness_profile: profile,
        categories: {
          ...categories,
          self_harm: true,
          illegal_acts_weapons_drugs: true,
        },
        allow_ncert_biology_reproduction: allowBiology,
        custom_blocked_keywords: keywords,
        custom_blocked_topics: settings?.custom_blocked_topics || [],
        session_timeout_minutes: timeoutMinutes,
      };

      const res = await fetch('/api/parent/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        setSettings(data);
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      } else {
        setError('Failed to update settings.');
      }
    } catch {
      setError('Network connection error while saving.');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: '#8e918f' }}>
        Loading content filtering preferences…
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* ── Strictness Presets ── */}
      <div>
        <div style={{ fontSize: '14px', fontWeight: 600, color: '#e3e3e3', marginBottom: '10px' }}>
          Strictness Presets
        </div>
        <div className="presets-grid">
          <div
            className={`preset-card ${profile === 'strict_elementary' ? 'active' : ''}`}
            onClick={() => handleSelectPreset('strict_elementary')}
          >
            <div className="preset-card-title">
              <span>🌱</span> Strict Elementary (Class 5)
            </div>
            <div className="preset-card-desc">
              Maximum restriction for elementary learners. Zero tolerance for mature themes; simplified textbook responses.
            </div>
          </div>

          <div
            className={`preset-card ${profile === 'curriculum_standard' ? 'active' : ''}`}
            onClick={() => handleSelectPreset('curriculum_standard')}
          >
            <div className="preset-card-title">
              <span>📖</span> Curriculum Standard (Class 10)
            </div>
            <div className="preset-card-desc">
              Recommended for board exam students. Preserves NCERT Biology reproduction science while strictly blocking inappropriate inquiries.
            </div>
          </div>

          <div
            className={`preset-card ${profile === 'custom' ? 'active' : ''}`}
            onClick={() => setProfile('custom')}
          >
            <div className="preset-card-title">
              <span>⚙️</span> Custom Rules
            </div>
            <div className="preset-card-desc">
              Tailor specific safety categories, custom blocked keywords, and timeout settings.
            </div>
          </div>
        </div>
      </div>

      {/* ── Category Toggles Panel ── */}
      <div className="filter-categories-panel">
        <div style={{ fontSize: '15px', fontWeight: 600, color: '#e3e3e3', marginBottom: '12px' }}>
          Safety Category Enforcement
        </div>

        {/* 1. Adult & Sexual */}
        <div className="filter-toggle-row">
          <div className="filter-toggle-info">
            <span className="filter-toggle-label">Adult & Sexual Content</span>
            <span className="filter-toggle-desc">
              Blocks explicit sexual descriptions, erotica, and non-educational anatomy inquiries.
            </span>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={Boolean(categories.adult_sexual)}
              onChange={() => handleToggleCategory('adult_sexual')}
            />
            <span className="slider"></span>
          </label>
        </div>

        {/* 2. Violence & Gore */}
        <div className="filter-toggle-row">
          <div className="filter-toggle-info">
            <span className="filter-toggle-label">Violence & Gore</span>
            <span className="filter-toggle-desc">
              Blocks graphic brutality, decapitation, torture, and assault descriptions.
            </span>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={Boolean(categories.violence_gore)}
              onChange={() => handleToggleCategory('violence_gore')}
            />
            <span className="slider"></span>
          </label>
        </div>

        {/* 3. Self-Harm & Suicide (PERMANENT LOCKED) */}
        <div className="filter-toggle-row">
          <div className="filter-toggle-info">
            <span className="filter-toggle-label">
              Self-Harm & Suicide Crisis 🔒
            </span>
            <span className="filter-toggle-desc" style={{ color: '#f28b82' }}>
              Permanent non-negotiable protection. Immediately refuses methods and presents Indian national crisis helplines.
            </span>
          </div>
          <label className="switch">
            <input type="checkbox" checked={true} disabled />
            <span className="slider"></span>
          </label>
        </div>

        {/* 4. Hate Speech */}
        <div className="filter-toggle-row">
          <div className="filter-toggle-info">
            <span className="filter-toggle-label">Hate Speech & Discrimination</span>
            <span className="filter-toggle-desc">
              Blocks religious hatred, caste slurs, hate symbols, and discriminatory stereotypes.
            </span>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={Boolean(categories.hate_speech)}
              onChange={() => handleToggleCategory('hate_speech')}
            />
            <span className="slider"></span>
          </label>
        </div>

        {/* 5. Weapons & Illegal Acts (PERMANENT LOCKED) */}
        <div className="filter-toggle-row">
          <div className="filter-toggle-info">
            <span className="filter-toggle-label">
              Weapons, Explosives & Illegal Acts 🔒
            </span>
            <span className="filter-toggle-desc" style={{ color: '#f28b82' }}>
              Permanent non-negotiable protection. Blocks bomb making, firearm synthesis, and illicit narcotic distribution.
            </span>
          </div>
          <label className="switch">
            <input type="checkbox" checked={true} disabled />
            <span className="slider"></span>
          </label>
        </div>

        {/* 6. Cyberbullying */}
        <div className="filter-toggle-row">
          <div className="filter-toggle-info">
            <span className="filter-toggle-label">Cyberbullying & Harassment</span>
            <span className="filter-toggle-desc">
              Blocks peer harassment, insults, defamation, and targeted humiliation.
            </span>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={Boolean(categories.cyberbullying)}
              onChange={() => handleToggleCategory('cyberbullying')}
            />
            <span className="slider"></span>
          </label>
        </div>

        {/* 7. Other Inappropriate */}
        <div className="filter-toggle-row">
          <div className="filter-toggle-info">
            <span className="filter-toggle-label">Other Inappropriate Themes</span>
            <span className="filter-toggle-desc">
              Blocks online gambling, underage tobacco/vaping, and severe vulgarity.
            </span>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={Boolean(categories.other_inappropriate)}
              onChange={() => handleToggleCategory('other_inappropriate')}
            />
            <span className="slider"></span>
          </label>
        </div>
      </div>

      {/* ── NCERT Biology Preservation Switch ── */}
      <div className="filter-categories-panel">
        <div className="filter-toggle-row" style={{ border: 'none', padding: 0 }}>
          <div className="filter-toggle-info">
            <span className="filter-toggle-label" style={{ fontSize: '15px' }}>
              🔬 Allow NCERT Class 10 Reproductive Biology (Chapter 7)
            </span>
            <span className="filter-toggle-desc">
              Preserves legitimate textbook topics: Human reproductive systems, gametes, menstruation, and contraception.
            </span>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={allowBiology}
              onChange={() => {
                setProfile('custom');
                setAllowBiology(!allowBiology);
              }}
            />
            <span className="slider"></span>
          </label>
        </div>

        <div className="biology-callout">
          <span>ℹ️</span>
          <div>
            <strong>Curriculum Alignment:</strong> When enabled, standard scientific questions from NCERT Class 10 Chapter 7 (*"How do Organisms Reproduce?"*) are answered accurately with textbook citations. Non-scientific pornography and explicit vulgarities remain strictly blocked at all times.
          </div>
        </div>
      </div>

      {/* ── Custom Blocked Keywords Manager ── */}
      <div className="keywords-panel">
        <div style={{ fontSize: '15px', fontWeight: 600, color: '#e3e3e3', marginBottom: '6px' }}>
          Custom Blocked Words & Slang
        </div>
        <div style={{ fontSize: '12px', color: '#8e918f', marginBottom: '14px' }}>
          Add custom terms, gaming sites, or topics you want blocked. Any student query containing these words will be politely refused.
        </div>

        <form onSubmit={handleAddKeyword} className="keywords-input-row">
          <input
            type="text"
            className="parental-input"
            style={{ flex: 1 }}
            placeholder="Add a word or phrase (e.g. gambling, roblox, vaping)…"
            value={newKeyword}
            onChange={(e) => setNewKeyword(e.target.value)}
          />
          <button
            type="submit"
            className="history-btn-secondary"
            style={{ background: '#8ab4f8', color: '#131314', fontWeight: 600 }}
            disabled={!newKeyword.trim()}
          >
            + Add Word
          </button>
        </form>

        <div className="keywords-chips-container">
          {keywords.length === 0 ? (
            <span style={{ fontSize: '12px', color: '#8e918f' }}>
              No custom keywords added yet.
            </span>
          ) : (
            keywords.map((word) => (
              <span key={word} className="keyword-chip">
                <span>{word}</span>
                <button
                  type="button"
                  className="keyword-chip-remove"
                  onClick={() => handleRemoveKeyword(word)}
                  title={`Remove "${word}"`}
                >
                  ✕
                </button>
              </span>
            ))
          )}
        </div>
      </div>

      {/* ── Notifications & Feedback ── */}
      {error && (
        <div className="parental-alert-msg parental-alert-error">
          <span>⚠️</span> {error}
        </div>
      )}
      {saveSuccess && (
        <div className="parental-alert-msg parental-alert-success">
          <span>✓</span> Safety settings saved successfully and active immediately.
        </div>
      )}

      {/* ── Save Settings Button ── */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
        <button
          type="button"
          className="parental-action-btn"
          style={{ width: 'auto', padding: '12px 28px' }}
          onClick={handleSaveSettings}
          disabled={isSaving}
        >
          {isSaving ? 'Saving Changes…' : 'Save Safety Settings'}
        </button>
      </div>
    </div>
  );
}
