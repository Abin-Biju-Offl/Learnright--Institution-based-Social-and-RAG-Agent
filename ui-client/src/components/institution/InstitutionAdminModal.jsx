import React, { useState, useEffect, useCallback } from 'react';
import './institution.css';

export default function InstitutionAdminModal({ isOpen, onClose, token, currentUser, onInstitutionUpdated }) {
  const [activeTab, setActiveTab] = useState('classes'); // 'classes' | 'invites' | 'faculty'
  const [instData, setInstData] = useState(null);
  const [facultyList, setFacultyList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Create institution state
  const [newInstName, setNewInstName] = useState('');
  const [newSchoolCode, setNewSchoolCode] = useState('');
  const [newLocation, setNewLocation] = useState('');
  const [newAcademicYear, setNewAcademicYear] = useState('2026-2027');
  const [newWebsite, setNewWebsite] = useState('');
  const [newAffiliationNumber, setNewAffiliationNumber] = useState('');
  const [newMediumOfInstruction, setNewMediumOfInstruction] = useState('English');
  const [newEducationLevels, setNewEducationLevels] = useState(['Primary', 'Middle', 'Secondary', 'Higher Secondary']);
  const [newAvailableClasses, setNewAvailableClasses] = useState('LKG–Grade 12');

  const toggleEducationLevel = (lvl) => {
    setNewEducationLevels((prev) =>
      prev.includes(lvl) ? prev.filter((x) => x !== lvl) : [...prev, lvl]
    );
  };

  // Create class state
  const [newGrade, setNewGrade] = useState(10);
  const [newClassDisplayName, setNewClassDisplayName] = useState('Class 10');

  // Create section state
  const [selectedClassId, setSelectedClassId] = useState('');
  const [newSectionName, setNewSectionName] = useState('A');
  const [newSectionRoom, setNewSectionRoom] = useState('');

  const isValidJwt = (t) => typeof t === 'string' && t.trim().split('.').length === 3;

  // Generate invite state
  const [inviteTargetRole, setInviteTargetRole] = useState('student');
  const [inviteClassId, setInviteClassId] = useState('');
  const [inviteSectionId, setInviteSectionId] = useState('');
  const [generatedInvite, setGeneratedInvite] = useState(null);

  const fetchInstitutionDetails = useCallback(async () => {
    if (!token || !isValidJwt(token)) {
      setInstData(null);
      return;
    }
    setLoading(true);
    setErrorMsg('');
    try {
      const res = await fetch('/api/institutions/me', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setInstData(data);
        if (data.classes && data.classes.length > 0) {
          if (!selectedClassId) setSelectedClassId(data.classes[0].id);
          if (!inviteClassId) setInviteClassId(data.classes[0].id);
        }
      } else if (res.status === 400 || res.status === 404) {
        setInstData(null);
      } else if (res.status === 401) {
        setErrorMsg('Admin authorization expired. Please re-select Org Admin in the demo menu or log in again.');
      }
    } catch {
      setErrorMsg('Failed to load institution details. Check network connection.');
    } finally {
      setLoading(false);
    }
  }, [token, selectedClassId, inviteClassId]);

  const fetchFaculty = useCallback(async () => {
    if (!token || !isValidJwt(token)) return;
    try {
      const res = await fetch('/api/institutions/faculty', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const list = await res.json();
        setFacultyList(list);
      }
    } catch {}
  }, [token]);

  useEffect(() => {
    if (isOpen) {
      setErrorMsg('');
      setSuccessMsg('');
      setGeneratedInvite(null);
      fetchInstitutionDetails();
      fetchFaculty();
    }
  }, [isOpen, fetchInstitutionDetails, fetchFaculty]);

  // Handle Create Institution
  const handleCreateInstitution = async (e) => {
    e.preventDefault();
    if (!newInstName.trim() || !newSchoolCode.trim()) {
      setErrorMsg('Please enter both School Name and School Code / ID.');
      return;
    }
    if (!token || !isValidJwt(token)) {
      setErrorMsg('Please select Org Admin in the bottom-left profile menu or sign in as Admin.');
      return;
    }
    setLoading(true);
    setErrorMsg('');
    try {
      const res = await fetch('/api/institutions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: newInstName.trim(),
          school_code: newSchoolCode.trim().toUpperCase(),
          location: newLocation.trim() || undefined,
          academic_year: newAcademicYear.trim() || '2026-2027',
          website: newWebsite.trim() || undefined,
          affiliation_number: newAffiliationNumber.trim() || undefined,
          medium_of_instruction: newMediumOfInstruction.trim() || 'English',
          education_levels: newEducationLevels,
          available_classes: newAvailableClasses.trim() || 'LKG–Grade 12',
        }),
      });
      if (res.ok) {
        setSuccessMsg('Institution registered successfully!');
        if (onInstitutionUpdated) onInstitutionUpdated();
        fetchInstitutionDetails();
        fetchFaculty();
      } else {
        const d = await res.json();
        setErrorMsg(d.detail || 'Failed to create institution.');
      }
    } catch {
      setErrorMsg('Network error creating institution.');
    } finally {
      setLoading(false);
    }
  };

  // Handle Add Class
  const handleAddClass = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    try {
      const res = await fetch('/api/institutions/classes', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          grade: Number(newGrade),
          display_name: newClassDisplayName.trim() || `Class ${newGrade}`,
        }),
      });
      if (res.ok) {
        setSuccessMsg(`Class ${newGrade} created!`);
        fetchInstitutionDetails();
      } else {
        const d = await res.json();
        setErrorMsg(d.detail || 'Failed to create class.');
      }
    } catch {
      setErrorMsg('Error creating class.');
    }
  };

  // Handle Add Section
  const handleAddSection = async (e) => {
    e.preventDefault();
    if (!selectedClassId) {
      setErrorMsg('Please select a Class first.');
      return;
    }
    setErrorMsg('');
    try {
      const res = await fetch(`/api/institutions/classes/${selectedClassId}/sections`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          section_name: newSectionName.trim().toUpperCase(),
          room: newSectionRoom.trim() || null,
        }),
      });
      if (res.ok) {
        setSuccessMsg(`Section ${newSectionName.toUpperCase()} added!`);
        fetchInstitutionDetails();
      } else {
        const d = await res.json();
        setErrorMsg(d.detail || 'Failed to add section.');
      }
    } catch {
      setErrorMsg('Error creating section.');
    }
  };

  // Handle Generate Invite
  const handleGenerateInvite = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setGeneratedInvite(null);
    try {
      const body = {
        target_role: inviteTargetRole,
        max_uses: 50,
        expires_days: 14,
      };
      if (inviteTargetRole === 'student') {
        if (!inviteClassId || !inviteSectionId) {
          setErrorMsg('Student invites require selecting both a Class and Section.');
          return;
        }
        body.class_id = inviteClassId;
        body.section_id = inviteSectionId;
      }
      const res = await fetch('/api/institutions/invites', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        const fullUrl = `${window.location.origin}/#join?invite=${data.token}`;
        setGeneratedInvite({ ...data, fullUrl });
        setSuccessMsg('Role-specific invite link generated!');
      } else {
        const d = await res.json();
        setErrorMsg(d.detail || 'Failed to generate invite link.');
      }
    } catch {
      setErrorMsg('Error generating invite link.');
    }
  };

  // Handle Assign Class Advisor
  const handleAssignAdvisor = async (sectionId, advisorId) => {
    try {
      const res = await fetch(`/api/institutions/sections/${sectionId}/advisor`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ advisor_user_id: advisorId || null }),
      });
      if (res.ok) {
        setSuccessMsg('Class Advisor updated!');
        fetchInstitutionDetails();
        fetchFaculty();
      } else {
        const d = await res.json();
        setErrorMsg(d.detail || 'Failed to assign Class Advisor.');
      }
    } catch {
      setErrorMsg('Error assigning Class Advisor.');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="inst-modal-overlay" onClick={onClose}>
      <div className="inst-modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="inst-modal-header">
          <div className="inst-modal-header-left">
            <h3 className="inst-modal-title">
              <span>🏛️</span>
              <span>{instData?.institution?.name || 'Institution Administration'}</span>
            </h3>
            {instData?.institution && (
              <span className="inst-status-pill">
                ID: {instData.institution.demo_verification_id}
              </span>
            )}
          </div>
          <button type="button" className="inst-close-btn" onClick={onClose}>✕</button>
        </div>

        {/* If no institution yet: Start Institution screen */}
        {!instData?.institution ? (
          <div className="inst-body" style={{ maxWidth: 660, margin: 'auto' }}>
            <div style={{ textAlign: 'center', marginBottom: 20 }}>
              <div style={{ fontSize: 44, marginBottom: 12 }}>🏫</div>
              <h2 style={{ fontSize: 24, fontWeight: 700, color: '#ffffff', margin: '0 0 6px 0' }}>
                Register Your Institution
              </h2>
              <p style={{ color: '#9aa0a6', fontSize: 14 }}>
                Set up your school organization to structure classes, assign faculty advisors, and manage student curriculum access.
              </p>
            </div>

            {errorMsg && (
              <div style={{ color: '#f28b82', background: 'rgba(242, 139, 130, 0.1)', padding: '10px 14px', borderRadius: 10, border: '1px solid rgba(242, 139, 130, 0.25)', marginBottom: 16 }}>
                ⚠️ {errorMsg}
              </div>
            )}
            {successMsg && (
              <div style={{ color: '#81c995', background: 'rgba(129, 201, 149, 0.1)', padding: '10px 14px', borderRadius: 10, border: '1px solid rgba(129, 201, 149, 0.25)', marginBottom: 16 }}>
                ✓ {successMsg}
              </div>
            )}

            <form onSubmit={handleCreateInstitution} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Section A: School Information */}
              <div className="inst-section-divider">
                <span style={{ fontSize: 15 }}>🏛️</span>
                <span className="inst-section-title">A. School Information</span>
              </div>

              <div className="inst-form-grid">
                <div className="inst-form-group">
                  <label className="inst-label">School Name *</label>
                  <input
                    type="text"
                    className="inst-input"
                    placeholder="e.g. Delhi Public School"
                    value={newInstName}
                    onChange={(e) => setNewInstName(e.target.value)}
                    required
                  />
                  <span className="inst-helper">Identifies the school across all classes</span>
                </div>

                <div className="inst-form-group">
                  <label className="inst-label">School Code / ID *</label>
                  <input
                    type="text"
                    className="inst-input"
                    placeholder="e.g. DPS-DELHI-01"
                    value={newSchoolCode}
                    onChange={(e) => setNewSchoolCode(e.target.value)}
                    required
                  />
                  <span className="inst-helper">Unique school code for student &amp; faculty joining</span>
                </div>

                <div className="inst-form-group">
                  <label className="inst-label">Location (Board &amp; Region)</label>
                  <input
                    type="text"
                    className="inst-input"
                    placeholder="e.g. R.K. Puram, New Delhi, India"
                    value={newLocation}
                    onChange={(e) => setNewLocation(e.target.value)}
                  />
                  <span className="inst-helper">Identifies education board &amp; regional context</span>
                </div>

                <div className="inst-form-group">
                  <label className="inst-label">Academic Year</label>
                  <select
                    className="inst-select"
                    value={newAcademicYear}
                    onChange={(e) => setNewAcademicYear(e.target.value)}
                  >
                    <option value="2026-2027">2026–2027 (Current Syllabus)</option>
                    <option value="2025-2026">2025–2026</option>
                    <option value="2027-2028">2027–2028</option>
                  </select>
                  <span className="inst-helper">Selects current syllabus &amp; academic cycle</span>
                </div>

                <div className="inst-form-group">
                  <label className="inst-label">Official Website</label>
                  <input
                    type="url"
                    className="inst-input"
                    placeholder="https://dpsdelhi.edu.in"
                    value={newWebsite}
                    onChange={(e) => setNewWebsite(e.target.value)}
                  />
                  <span className="inst-helper">Verifies official school accreditation</span>
                </div>

                <div className="inst-form-group">
                  <label className="inst-label">School Affiliation Number</label>
                  <input
                    type="text"
                    className="inst-input"
                    placeholder="e.g. CBSE/AFF/2026/89410"
                    value={newAffiliationNumber}
                    onChange={(e) => setNewAffiliationNumber(e.target.value)}
                  />
                  <span className="inst-helper">Verifies board affiliation record</span>
                </div>

                <div className="inst-form-group" style={{ gridColumn: 'span 2' }}>
                  <label className="inst-label">Medium of Instruction</label>
                  <select
                    className="inst-select"
                    value={newMediumOfInstruction}
                    onChange={(e) => setNewMediumOfInstruction(e.target.value)}
                  >
                    <option value="English">English</option>
                    <option value="Hindi">Hindi</option>
                    <option value="Bilingual">Bilingual (English &amp; Hindi)</option>
                  </select>
                  <span className="inst-helper">Default language for curriculum textbooks and explanations</span>
                </div>
              </div>

              {/* Section B: Academic Structure */}
              <div className="inst-section-divider" style={{ marginTop: 14 }}>
                <span style={{ fontSize: 15 }}>📚</span>
                <span className="inst-section-title">B. Academic Structure</span>
              </div>

              <div className="inst-form-group">
                <label className="inst-label">Education Levels Supported</label>
                <div className="inst-level-chips">
                  {['Primary', 'Middle', 'Secondary', 'Higher Secondary'].map((lvl) => {
                    const active = newEducationLevels.includes(lvl);
                    return (
                      <button
                        key={lvl}
                        type="button"
                        className={`inst-level-chip ${active ? 'active' : ''}`}
                        onClick={() => toggleEducationLevel(lvl)}
                      >
                        {active ? '✓ ' : '+ '}{lvl}
                      </button>
                    );
                  })}
                </div>
                <span className="inst-helper">Click to toggle active educational tiers</span>
              </div>

              <div className="inst-form-group">
                <label className="inst-label">Available Classes Span</label>
                <input
                  type="text"
                  className="inst-input"
                  placeholder="e.g. LKG–Grade 12 or Grade 1–10"
                  value={newAvailableClasses}
                  onChange={(e) => setNewAvailableClasses(e.target.value)}
                />
                <span className="inst-helper">Span of grades offered by your institution</span>
              </div>

              <button
                type="submit"
                className="inst-btn inst-btn-primary"
                disabled={loading}
                style={{ justifyContent: 'center', marginTop: 14, height: 46, fontSize: 15 }}
              >
                {loading ? 'Registering School…' : '🚀 Launch Institution (Org Admin)'}
              </button>
            </form>
          </div>
        ) : (
          <>
            {/* Tabs Bar */}
            <nav className="inst-tabs">
              <button
                type="button"
                className={`inst-tab ${activeTab === 'classes' ? 'active' : ''}`}
                onClick={() => setActiveTab('classes')}
              >
                <span>📚</span> Classes &amp; Sections
              </button>
              <button
                type="button"
                className={`inst-tab ${activeTab === 'invites' ? 'active' : ''}`}
                onClick={() => setActiveTab('invites')}
              >
                <span>🔗</span> Role-Specific Invites
              </button>
              <button
                type="button"
                className={`inst-tab ${activeTab === 'faculty' ? 'active' : ''}`}
                onClick={() => setActiveTab('faculty')}
              >
                <span>👨‍🏫</span> Faculty &amp; Class Advisors
              </button>
            </nav>

            {/* Body */}
            <div className="inst-body">
              {/* Feedback messages */}
              {errorMsg && <div style={{ color: '#f28b82', marginBottom: 14 }}>⚠️ {errorMsg}</div>}
              {successMsg && <div style={{ color: '#81c995', marginBottom: 14 }}>✓ {successMsg}</div>}

              {/* Statistics Overview */}
              <div className="inst-stat-grid">
                <div className="inst-stat-card">
                  <div className="inst-stat-icon">🎓</div>
                  <div>
                    <h4 className="inst-stat-value">{instData.total_students || 0}</h4>
                    <p className="inst-stat-label">Enrolled Students</p>
                  </div>
                </div>
                <div className="inst-stat-card">
                  <div className="inst-stat-icon">👨‍🏫</div>
                  <div>
                    <h4 className="inst-stat-value">{instData.total_faculty || 0}</h4>
                    <p className="inst-stat-label">Faculty Lecturers</p>
                  </div>
                </div>
                <div className="inst-stat-card">
                  <div className="inst-stat-icon">🏫</div>
                  <div>
                    <h4 className="inst-stat-value">{instData.classes?.length || 0}</h4>
                    <p className="inst-stat-label">Active Classes</p>
                  </div>
                </div>
              </div>

              {/* ── TAB 1: Classes & Sections ── */}
              {activeTab === 'classes' && (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
                    {/* Add Class Form */}
                    <div className="inst-card-panel">
                      <h4 className="inst-card-title">➕ Add Class</h4>
                      <form onSubmit={handleAddClass}>
                        <div className="inst-form-row">
                          <div className="inst-form-group">
                            <label className="inst-label">Grade</label>
                            <select
                              className="inst-select"
                              value={newGrade}
                              onChange={(e) => {
                                setNewGrade(e.target.value);
                                setNewClassDisplayName(`Class ${e.target.value}`);
                              }}
                            >
                              {[...Array(12)].map((_, i) => (
                                <option key={i + 1} value={i + 1}>Grade {i + 1}</option>
                              ))}
                            </select>
                          </div>
                          <div className="inst-form-group">
                            <label className="inst-label">Display Name</label>
                            <input
                              type="text"
                              className="inst-input"
                              value={newClassDisplayName}
                              onChange={(e) => setNewClassDisplayName(e.target.value)}
                              placeholder="Class 10"
                            />
                          </div>
                          <button type="submit" className="inst-btn inst-btn-primary">Add Class</button>
                        </div>
                      </form>
                    </div>

                    {/* Add Section Form */}
                    <div className="inst-card-panel">
                      <h4 className="inst-card-title">➕ Add Section</h4>
                      <form onSubmit={handleAddSection}>
                        <div className="inst-form-row">
                          <div className="inst-form-group">
                            <label className="inst-label">Target Class</label>
                            <select
                              className="inst-select"
                              value={selectedClassId}
                              onChange={(e) => setSelectedClassId(e.target.value)}
                            >
                              {instData.classes?.map((c) => (
                                <option key={c.id} value={c.id}>{c.display_name}</option>
                              ))}
                            </select>
                          </div>
                          <div className="inst-form-group" style={{ maxWidth: 80 }}>
                            <label className="inst-label">Section</label>
                            <input
                              type="text"
                              className="inst-input"
                              value={newSectionName}
                              onChange={(e) => setNewSectionName(e.target.value)}
                              placeholder="A"
                              required
                            />
                          </div>
                          <div className="inst-form-group">
                            <label className="inst-label">Room (Optional)</label>
                            <input
                              type="text"
                              className="inst-input"
                              value={newSectionRoom}
                              onChange={(e) => setNewSectionRoom(e.target.value)}
                              placeholder="Room 101"
                            />
                          </div>
                          <button type="submit" className="inst-btn inst-btn-primary">Add Section</button>
                        </div>
                      </form>
                    </div>
                  </div>

                  {/* Classes Tree */}
                  <h4 className="inst-card-title">Academic Hierarchy (Classes &amp; Sections)</h4>
                  {instData.classes?.length === 0 ? (
                    <div style={{ color: '#8e918f', fontStyle: 'italic' }}>No classes created yet. Add one above!</div>
                  ) : (
                    instData.classes?.map((c) => (
                      <div key={c.id} className="class-tree-item">
                        <div className="class-tree-header">
                          <span className="class-tree-title">
                            <span>📖</span> {c.display_name} (Grade {c.grade})
                          </span>
                          <span style={{ fontSize: 12, color: '#8e918f' }}>
                            {c.sections?.length || 0} section(s)
                          </span>
                        </div>
                        <div className="section-chip-grid">
                          {c.sections?.map((s) => (
                            <div key={s.id} className="section-chip">
                              <span className="section-chip-name">Section {s.section_name}</span>
                              <span className="section-chip-meta">{s.room || 'No Room assigned'} · {s.student_count || 0} students</span>
                              <span className="section-chip-advisor">
                                {s.class_advisor_name ? `Advisor: ${s.class_advisor_name}` : 'No Advisor assigned'}
                              </span>
                            </div>
                          ))}
                          {(!c.sections || c.sections.length === 0) && (
                            <span style={{ fontSize: 12, color: '#8e918f' }}>No sections added to this class.</span>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* ── TAB 2: Role-Specific Invites ── */}
              {activeTab === 'invites' && (
                <div>
                  <div className="inst-card-panel">
                    <h4 className="inst-card-title">🔗 Generate Role-Specific Invite Link</h4>
                    <form onSubmit={handleGenerateInvite}>
                      <div className="inst-form-row">
                        <div className="inst-form-group">
                          <label className="inst-label">Role to Invite</label>
                          <select
                            className="inst-select"
                            value={inviteTargetRole}
                            onChange={(e) => setInviteTargetRole(e.target.value)}
                          >
                            <option value="student">Student (Enrolls in specific class/section)</option>
                            <option value="lecturer">Lecturer / Faculty (Multi-grade access)</option>
                          </select>
                        </div>

                        {inviteTargetRole === 'student' && (
                          <>
                            <div className="inst-form-group">
                              <label className="inst-label">Class</label>
                              <select
                                className="inst-select"
                                value={inviteClassId}
                                onChange={(e) => {
                                  setInviteClassId(e.target.value);
                                  const cl = instData.classes?.find((x) => x.id === e.target.value);
                                  if (cl && cl.sections && cl.sections.length > 0) {
                                    setInviteSectionId(cl.sections[0].id);
                                  }
                                }}
                              >
                                {instData.classes?.map((c) => (
                                  <option key={c.id} value={c.id}>{c.display_name}</option>
                                ))}
                              </select>
                            </div>

                            <div className="inst-form-group">
                              <label className="inst-label">Section</label>
                              <select
                                className="inst-select"
                                value={inviteSectionId}
                                onChange={(e) => setInviteSectionId(e.target.value)}
                              >
                                {instData.classes
                                  ?.find((c) => c.id === inviteClassId)
                                  ?.sections?.map((s) => (
                                    <option key={s.id} value={s.id}>Section {s.section_name}</option>
                                  ))}
                              </select>
                            </div>
                          </>
                        )}

                        <button type="submit" className="inst-btn inst-btn-primary">Generate Link</button>
                      </div>
                    </form>

                    {generatedInvite && (
                      <div className="invite-url-box">
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 11, color: '#9aa0a6', marginBottom: 4 }}>
                            {generatedInvite.target_role.toUpperCase()} INVITE LINK
                            {generatedInvite.section_name && ` (Section ${generatedInvite.section_name})`}
                          </div>
                          <div className="invite-url-text">{generatedInvite.fullUrl}</div>
                        </div>
                        <button
                          type="button"
                          className="inst-btn inst-btn-secondary"
                          onClick={() => {
                            navigator.clipboard.writeText(generatedInvite.fullUrl);
                            setSuccessMsg('Invite link copied to clipboard!');
                            setTimeout(() => setSuccessMsg(''), 2500);
                          }}
                        >
                          📋 Copy Link
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* ── TAB 3: Faculty & Class Advisors ── */}
              {activeTab === 'faculty' && (
                <div>
                  <h4 className="inst-card-title">👨‍🏫 Faculty Members &amp; Class Advisors</h4>
                  <p style={{ color: '#9aa0a6', fontSize: 13, marginBottom: 16 }}>
                    Lecturers have multi-grade textbook access. The <strong>Class Advisor</strong> is the teacher in charge of monitoring a specific class/section.
                  </p>

                  <div className="inst-card-panel">
                    <h5 style={{ color: '#e3e3e3', fontSize: 14, margin: '0 0 12px 0' }}>Assign Class Advisor to Sections</h5>
                    {instData.classes?.flatMap((c) => c.sections).map((sec) => (
                      <div key={sec.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                        <div>
                          <strong style={{ color: '#ffffff' }}>Section {sec.section_name}</strong>
                          <span style={{ color: '#8e918f', fontSize: 12, marginLeft: 8 }}>
                            ({sec.student_count || 0} students)
                          </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <span style={{ fontSize: 12, color: '#9aa0a6' }}>Class Advisor:</span>
                          <select
                            className="inst-select"
                            value={sec.class_advisor_id || ''}
                            onChange={(e) => handleAssignAdvisor(sec.id, e.target.value)}
                            style={{ minWidth: 180 }}
                          >
                            <option value="">-- No Advisor Assigned --</option>
                            {facultyList.map((f) => (
                              <option key={f.id} value={f.id}>
                                {f.full_name || f.username} ({f.role === 'org_admin' ? 'Admin' : 'Lecturer'})
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="inst-card-panel">
                    <h5 style={{ color: '#e3e3e3', fontSize: 14, margin: '0 0 12px 0' }}>Faculty Roster &amp; Subject Tags</h5>
                    {facultyList.map((fac) => (
                      <div key={fac.id} style={{ padding: '12px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <div>
                            <strong style={{ color: '#ffffff', fontSize: 14 }}>{fac.full_name || fac.username}</strong>
                            <span style={{ marginLeft: 8, fontSize: 11, padding: '2px 8px', borderRadius: 10, background: 'rgba(138,180,248,0.15)', color: '#8ab4f8' }}>
                              {fac.role === 'org_admin' ? 'Principal / Headmaster' : 'Lecturer'}
                            </span>
                          </div>
                          <div>
                            {fac.advised_sections?.map((adv, idx) => (
                              <span key={idx} style={{ fontSize: 11, color: '#81c995', background: 'rgba(129,201,149,0.15)', padding: '2px 8px', borderRadius: 8, marginRight: 6 }}>
                                ⭐ Advisor: {adv.class_name} ({adv.section_name})
                              </span>
                            ))}
                          </div>
                        </div>
                        <div style={{ marginTop: 6 }}>
                          {fac.subject_tags?.map((tag, i) => (
                            <span key={i} className="inst-tag-pill">{tag}</span>
                          ))}
                          {(!fac.subject_tags || fac.subject_tags.length === 0) && (
                            <span style={{ fontSize: 12, color: '#8e918f', fontStyle: 'italic' }}>No subject tags set</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

