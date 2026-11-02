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
  const [newInstDemoId, setNewInstDemoId] = useState('');

  // Create class state
  const [newGrade, setNewGrade] = useState(10);
  const [newClassDisplayName, setNewClassDisplayName] = useState('Class 10');

  // Create section state
  const [selectedClassId, setSelectedClassId] = useState('');
  const [newSectionName, setNewSectionName] = useState('A');
  const [newSectionRoom, setNewSectionRoom] = useState('');

  // Generate invite state
  const [inviteTargetRole, setInviteTargetRole] = useState('student');
  const [inviteClassId, setInviteClassId] = useState('');
  const [inviteSectionId, setInviteSectionId] = useState('');
  const [generatedInvite, setGeneratedInvite] = useState(null);

  const fetchInstitutionDetails = useCallback(async () => {
    if (!token) return;
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
      }
    } catch {
      setErrorMsg('Failed to load institution details. Check network connection.');
    } finally {
      setLoading(false);
    }
  }, [token, selectedClassId, inviteClassId]);

  const fetchFaculty = useCallback(async () => {
    if (!token) return;
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
    if (!newInstName.trim() || !newInstDemoId.trim()) {
      setErrorMsg('Please enter both Institution Name and Demo Verification ID.');
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
          demo_verification_id: newInstDemoId.trim(),
        }),
      });
      if (res.ok) {
        setSuccessMsg('Institution created successfully!');
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
          <div className="inst-body" style={{ maxWidth: 540, margin: 'auto', textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>🏫</div>
            <h2 style={{ fontSize: 24, fontWeight: 700, color: '#ffffff', margin: '0 0 8px 0' }}>
              Start an Institution
            </h2>
            <p style={{ color: '#9aa0a6', fontSize: 14, marginBottom: 24 }}>
              Register your school or academy to structure classes, assign lecturers, and invite students.
            </p>

            {errorMsg && <div style={{ color: '#f28b82', marginBottom: 16 }}>{errorMsg}</div>}
            {successMsg && <div style={{ color: '#81c995', marginBottom: 16 }}>{successMsg}</div>}

            <form onSubmit={handleCreateInstitution} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="inst-form-group" style={{ textAlign: 'left' }}>
                <label className="inst-label">School / Institution Name</label>
                <input
                  type="text"
                  className="inst-input"
                  placeholder="e.g. Delhi Public School, R.K. Puram"
                  value={newInstName}
                  onChange={(e) => setNewInstName(e.target.value)}
                  required
                />
              </div>

              <div className="inst-form-group" style={{ textAlign: 'left' }}>
                <label className="inst-label">Demo Verification ID / Code</label>
                <input
                  type="text"
                  className="inst-input"
                  placeholder="e.g. DPS-2026-DEMO"
                  value={newInstDemoId}
                  onChange={(e) => setNewInstDemoId(e.target.value)}
                  required
                />
              </div>

              <button type="submit" className="inst-btn inst-btn-primary" style={{ justifyContent: 'center', marginTop: 10 }}>
                🚀 Launch Institution (Org Admin)
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
