import { useState, useEffect } from "react";
import "./App.css";

function App() {
  const [question, setQuestion] = useState("");
  const [activePage, setActivePage] = useState("dashboard");
  const [patients, setPatients] = useState([]);
  const [patientsLoading, setPatientsLoading] = useState(false);
  const [patientError, setPatientError] = useState("");
  const [patientSearch, setPatientSearch] = useState("");
  const [showAddPatient, setShowAddPatient] = useState(false);
  const [registeringPatient, setRegisteringPatient] = useState(false);
  const [registrationMessage, setRegistrationMessage] = useState("");
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [patientDetailsLoading, setPatientDetailsLoading] = useState(false);
  const [patientDetailsError, setPatientDetailsError] = useState("");
  const [editingPatient, setEditingPatient] = useState(false);
  const [savingPatient, setSavingPatient] = useState(false);

  const handleViewPatient = async (patientId) => {
    setPatientDetailsLoading(true);
    setPatientDetailsError("");
    setSelectedPatient(null);
    setEditingPatient(false);

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/patients/${encodeURIComponent(patientId)}`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to retrieve patient details."
        );
      }

      setSelectedPatient(data);
    } catch (err) {
      setPatientDetailsError(err.message);
    } finally {
      setPatientDetailsLoading(false);
    }
  };

  const handleUpdatePatient = async (e) => {
    e.preventDefault();

    if (!selectedPatient) return;

    setSavingPatient(true);
    setPatientDetailsError("");

    try {
      const formData = new FormData(e.currentTarget);
      const patientData = Object.fromEntries(formData.entries());

      // Convert empty date and age fields to null.
      patientData.Date_of_Birth =
        patientData.Date_of_Birth || null;

      patientData.Registration_Date =
        patientData.Registration_Date || null;

      patientData.Age =
        patientData.Age === "" ? null : Number(patientData.Age);

      const response = await fetch(
        `http://127.0.0.1:8000/patients/${encodeURIComponent(selectedPatient.Patient_ID)}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(patientData),
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          Array.isArray(result.detail)
            ? result.detail.map((item) => item.msg).join(", ")
            : result.detail || "Patient update failed."
        );
      }

      setSelectedPatient(result);
      setEditingPatient(false);

      // Refresh the patient table.
      const patientsResponse = await fetch(
        "http://127.0.0.1:8000/patients"
      );

      if (!patientsResponse.ok) {
        throw new Error(
          "Patient updated, but the patient list could not be refreshed."
        );
      }

      const updatedPatients = await patientsResponse.json();
      setPatients(updatedPatients);
    } catch (err) {
      setPatientDetailsError(err.message);
    } finally {
      setSavingPatient(false);
    }
  };

  const handleRegisterPatient = async (e) => {
    e.preventDefault();

    setRegisteringPatient(true);
    setRegistrationMessage("");

    try {
      const form = e.currentTarget;
      const formData = new FormData(form);
      const patientData = {};

      for (const [key, value] of formData.entries()) {
        const trimmedValue = value.trim();

        // Skip empty optional fields
        if (trimmedValue === "") continue;

        patientData[key] = trimmedValue;
      }

      // Convert age from string to number
      if (patientData.Age !== undefined) {
        patientData.Age = Number(patientData.Age);
      }

      const response = await fetch("http://127.0.0.1:8000/patients", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(patientData),
      });

      const result = await response.json();

      if (!response.ok) {
        const errorDetail = Array.isArray(result.detail)
          ? result.detail.map((item) => item.msg).join(", ")
          : result.detail || "Patient registration failed.";

        throw new Error(errorDetail);
      }

      // Refresh the patient list
      const patientsResponse = await fetch("http://127.0.0.1:8000/patients");

      if (!patientsResponse.ok) {
        throw new Error(
          "Patient registered, but the records list could not be refreshed. Please reload the page."
        );
      }

      const updatedPatients = await patientsResponse.json();
      setPatients(updatedPatients);

      form.reset();
      setShowAddPatient(false);

      setRegistrationMessage(
        `Patient registered successfully! Patient ID: ${result.Patient_ID}`
      );
    } catch (err) {
      setRegistrationMessage(err.message);
    } finally {
      setRegisteringPatient(false);
    }
  };

  const filteredPatients = patients.filter((patient) => {
    const search = patientSearch.trim().toLowerCase();

    if (!search) return true;

    return [
      patient.Patient_ID,
      patient.Full_Name,
      patient.Contact_Number,
      patient.Department,
    ].some((value) => String(value || "").toLowerCase().includes(search));
  });

  useEffect(() => {
    if (activePage !== "patients") return;

    const fetchPatients = async () => {
      setPatientsLoading(true);
      setPatientError("");

      try {
        const response = await fetch("http://127.0.0.1:8000/patients");

        if (!response.ok) {
          throw new Error("Failed to retrieve patient records.");
        }

        const data = await response.json();
        setPatients(data);
      } catch (err) {
        setPatientError(
          err.message === "Failed to fetch"
            ? "Cannot connect to the backend. Check whether FastAPI is running."
            : err.message
        );
      } finally {
        setPatientsLoading(false);
      }
    };

    fetchPatients();
  }, [activePage]);

  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSend = async () => {
    const submittedQuestion = question.trim();
    if (!submittedQuestion || loading) return;

    setLoading(true);
    setQuestion("");
    setError("");
    setMessages((currentMessages) => [
      ...currentMessages,
      { role: "user", content: submittedQuestion },
    ]);

    try {
      const response = await fetch("http://127.0.0.1:8000/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: submittedQuestion,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Something went wrong.");
      }

      setMessages((currentMessages) => [
        ...currentMessages,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources || [],
          warnings: data.warnings || [],
          validationStatus: data.validation_status || "not_applicable",
        },
      ]);
    } catch (err) {
      setError(
        err.message === "Failed to fetch"
          ? "Cannot connect to the backend. Please check whether FastAPI is running."
          : err.message
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon">✚</div>
          <div>
            <h2>MediCare</h2>
            <p>Hospital Portal</p>
          </div>
        </div>

        <div className="sidebar-menu">
          <p className="sidebar-heading">MAIN MENU</p>

          <button
            className={`sidebar-link ${activePage === "dashboard" ? "active" : ""}`}
            onClick={() => setActivePage("dashboard")}
          >
            <span className="sidebar-icon">▦</span> Dashboard
          </button>

          <button
            className={`sidebar-link ${activePage === "chat" ? "active" : ""}`}
            onClick={() => setActivePage("chat")}
          >
            <span className="sidebar-icon">💬</span> Chat Assistant
          </button>

          <p className="sidebar-heading">HOSPITAL</p>

          <button
            className={`sidebar-link ${activePage === "patients" ? "active" : ""}`}
            onClick={() => setActivePage("patients")}
          >
            <span className="sidebar-icon">♙</span> Patient Records
          </button>

          <button className="sidebar-link" disabled>
            <span className="sidebar-icon">▣</span> Appointments
          </button>

          <button className="sidebar-link" disabled>
            <span className="sidebar-icon">⚕</span> Laboratory
          </button>

          <button className="sidebar-link" disabled>
            <span className="sidebar-icon">◷</span> Duty Roster
          </button>

          <p className="sidebar-heading">PREFERENCES</p>

          <button className="sidebar-link" disabled>
            <span className="sidebar-icon">⚙</span> Settings
          </button>
        </div>

        <div className="sidebar-footer">
          <span className="status-dot"></span>
          AI Assistant System
          <small>Local environment</small>
        </div>
      </aside>

      <div className="main-content">
      <header className="topbar">
        <div className="topbar-title">
          <span className="topbar-eyebrow">MEDICARE HOSPITAL PORTAL</span>
          <h1>
            {activePage === "dashboard"
              ? "Dashboard"
              : activePage === "patients"
                ? "Patient Management"
                : "Chat Assistant"}
          </h1>
          <p>
            {activePage === "dashboard"
              ? "Hospital information and system overview"
              : activePage === "patients"
                ? "Manage and retrieve patient records"
                : "Ask questions about hospital information"}
          </p>
        </div>

        <div className="system-status">
          <span className="system-status-dot"></span>
          AI System Online
        </div>
      </header>

      {activePage === "dashboard" ? (
        <section className="dashboard-page">
          <div className="dashboard-heading">
            <span className="dashboard-tag">HOSPITAL OVERVIEW</span>
            <h1>Welcome to MediCare</h1>
            <p>
              Your central place to access hospital information and AI assistance.
            </p>
          </div>

          <div className="dashboard-stats">
            <div className="dashboard-card">
              <span className="dashboard-card-icon">📚</span>
              <h3>Knowledge Base</h3>
              <strong>3</strong>
              <p>Demo documents indexed</p>
            </div>

            <div className="dashboard-card">
              <span className="dashboard-card-icon">🤖</span>
              <h3>AI Model</h3>
              <strong>Llama 3.2</strong>
              <p>Running locally through Ollama</p>
            </div>

            <div className="dashboard-card">
              <span className="dashboard-card-icon">✓</span>
              <h3>Answer Validation</h3>
              <strong>Enabled</strong>
              <p>Claim-level citation review</p>
            </div>
          </div>

          <div className="dashboard-actions">
            <h2>Quick Access</h2>
            <p>Choose a service to get started.</p>

            <button
              className="dashboard-action-card"
              onClick={() => setActivePage("chat")}
            >
              <span>💬</span>
              <strong>Chat with AI Assistant</strong>
              <small>Ask questions about hospital documents and procedures.</small>
              <span className="dashboard-action-link">Open assistant →</span>
            </button>
          </div>
        </section>
      ) : activePage === "patients" ? (
        <section className="dashboard-page">
          <div className="dashboard-heading">
            <span className="dashboard-tag">HOSPITAL MANAGEMENT</span>
            <h1>Patient Records</h1>
            <p>View, search and manage registered patient information.</p>
          </div>

          <div className="patient-toolbar">
            <div className="patient-search">
              <input
                type="text"
                placeholder="Search by patient ID, name, contact or department..."
                value={patientSearch}
                onChange={(e) => setPatientSearch(e.target.value)}
              />
            </div>

            <div className="patient-count">
              Total Patients: <strong>{patients.length}</strong>
            </div>

            <button
              className="add-patient-button"
              onClick={() => {
                setShowAddPatient(!showAddPatient);
                setRegistrationMessage("");
              }}
            >
              + Add New Patient
            </button>
          </div>

          {registrationMessage && (
            <div
              className={
                registrationMessage.startsWith("Patient registered successfully")
                  ? "registration-success"
                  : "registration-error"
              }
            >
              {registrationMessage}
            </div>
          )}

          {patientDetailsLoading && (
            <div className="patient-details-container">
              Loading patient details...
            </div>
          )}

          {patientDetailsError && (
            <div className="registration-error">
              {patientDetailsError}
            </div>
          )}

          {selectedPatient && !patientDetailsLoading && (
            <div className="patient-details-container">
              <div className="patient-details-heading">
                <div>
                  <span className="dashboard-tag">PATIENT INFORMATION</span>
                  <h2>{selectedPatient.Full_Name}</h2>
                  <p>Patient ID: {selectedPatient.Patient_ID}</p>
                </div>

                <div className="patient-details-actions">
                  <button
                    type="button"
                    onClick={() => setEditingPatient(true)}
                  >
                    Edit Patient
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setSelectedPatient(null);
                      setEditingPatient(false);
                      setPatientDetailsError("");
                    }}
                  >
                    Close
                  </button>
                </div>
              </div>

              <div className="patient-details-grid">
                {[
                  ["Date of Birth", "Date_of_Birth"],
                  ["Age", "Age"],
                  ["Gender", "Gender"],
                  ["Contact Number", "Contact_Number"],
                  ["Address", "Address"],
                  ["Emergency Contact Name", "Emergency_Contact_Name"],
                  ["Emergency Contact Number", "Emergency_Contact_Number"],
                  ["Department", "Department"],
                  ["Doctor Assigned", "Doctor_Assigned"],
                  ["Registration Date", "Registration_Date"],
                  ["Visit Type", "Visit_Type"],
                  ["Record Status", "Record_Status"],
                  ["Notes", "Notes"],
                ].map(([label, field]) => (
                  <div className="patient-detail-item" key={field}>
                    <span>{label}</span>
                    <strong>{selectedPatient[field] || "—"}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}

          {showAddPatient && (
            <div className="patient-form-container">
              <div className="patient-form-heading">
                <div>
                  <h2>Register New Patient</h2>
                  <p>Enter the patient's registration details.</p>
                </div>

                <button
                  type="button"
                  className="patient-form-close"
                  aria-label="Close registration form"
                  onClick={() => setShowAddPatient(false)}
                >
                  ×
                </button>
              </div>

              <form className="patient-form" onSubmit={handleRegisterPatient}>
                <div className="patient-form-grid">
                  <label>
                    Full Name *
                    <input
                      type="text"
                      name="Full_Name"
                      placeholder="Enter full name"
                      required
                    />
                  </label>

                  <label>
                    Date of Birth
                    <input type="date" name="Date_of_Birth" />
                  </label>

                  <label>
                    Age
                    <input type="number" name="Age" min="0" max="150" />
                  </label>

                  <label>
                    Gender
                    <select name="Gender" defaultValue="">
                      <option value="" disabled>Select gender</option>
                      <option>Female</option>
                      <option>Male</option>
                      <option>Other</option>
                      <option>Prefer not to say</option>
                    </select>
                  </label>

                  <label>
                    Contact Number
                    <input type="tel" name="Contact_Number" />
                  </label>

                  <label>
                    Department
                    <input type="text" name="Department" />
                  </label>

                  <label>
                    Doctor Assigned
                    <input type="text" name="Doctor_Assigned" />
                  </label>

                  <label>
                    Emergency Contact Name
                    <input type="text" name="Emergency_Contact_Name" />
                  </label>

                  <label>
                    Emergency Contact Number
                    <input type="tel" name="Emergency_Contact_Number" />
                  </label>

                  <label>
                    Visit Type
                    <select name="Visit_Type" defaultValue="OPD">
                      <option>OPD</option>
                      <option>IPD</option>
                      <option>Emergency</option>
                      <option>Follow-up</option>
                    </select>
                  </label>

                  <label>
                    Record Status
                    <select name="Record_Status" defaultValue="Active">
                      <option>Active</option>
                      <option>Discharged</option>
                      <option>Inactive</option>
                    </select>
                  </label>

                  <label className="patient-full-width">
                    Address
                    <textarea name="Address" rows="2" />
                  </label>

                  <label className="patient-full-width">
                    Notes
                    <textarea name="Notes" rows="2" />
                  </label>
                </div>

                <div className="patient-form-actions">
                  <button
                    type="button"
                    onClick={() => setShowAddPatient(false)}
                  >
                    Cancel
                  </button>

                  <button type="submit" disabled={registeringPatient}>
                    {registeringPatient ? "Registering..." : "Register Patient"}
                  </button>
                </div>
              </form>
            </div>
          )}

          {patientsLoading && (
            <p>Loading patient records...</p>
          )}

          {patientError && (
            <div className="error-message">
              <strong>Error:</strong> {patientError}
            </div>
          )}

          {!patientsLoading && !patientError && (
            <div className="patient-table-container">
              <table className="patient-table">
                <thead>
                  <tr>
                    <th>Patient ID</th>
                    <th>Full Name</th>
                    <th>Age</th>
                    <th>Gender</th>
                    <th>Contact Number</th>
                    <th>Department</th>
                    <th>Status</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredPatients.map((patient) => (
                    <tr key={patient.Patient_ID}>
                      <td>
                        <button
                          type="button"
                          className="patient-id-link"
                          onClick={() => handleViewPatient(patient.Patient_ID)}
                        >
                          {patient.Patient_ID}
                        </button>
                      </td>
                      <td>{patient.Full_Name}</td>
                      <td>{patient.Age ?? "—"}</td>
                      <td>{patient.Gender || "—"}</td>
                      <td>{patient.Contact_Number || "—"}</td>
                      <td>{patient.Department || "—"}</td>
                      <td>
                        <span className="patient-status">
                          {patient.Record_Status || "—"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {filteredPatients.length === 0 && (
                <div className="patient-empty-state">
                  {patients.length === 0
                    ? "No patient records available yet."
                    : "No patients match your search."}
                </div>
              )}
            </div>
          )}
        </section>
      ) : (
        <>
      <main className="chat-container">
        {messages.length === 0 && (
          <div className="welcome-message">
            <div className="welcome-icon">✚</div>

            <span className="welcome-tag">
              AI POWERED HEALTHCARE ASSISTANT
            </span>

            <h2>How can I help you today?</h2>

            <p>
              Get reliable information about hospital procedures,
              laboratory rules, and staff duty schedules.
            </p>

            <div className="quick-prompts-label">SUGGESTED QUESTIONS</div>

            <div className="prompt-grid">
              <button
                className="suggestion-card"
                onClick={() => setQuestion("What are the lab timings?")}
              >
                <span>🧪</span>
                <strong>Laboratory timings</strong>
                <small>Check laboratory working hours</small>
              </button>

              <button
                className="suggestion-card"
                onClick={() => setQuestion("What are the shift timings?")}
              >
                <span>🕒</span>
                <strong>Staff duty timings</strong>
                <small>View morning, evening and night shifts</small>
              </button>

              <button
                className="suggestion-card"
                onClick={() =>
                  setQuestion("What are the requirements for new patient registration?")
                }
              >
                <span>📋</span>
                <strong>Patient registration</strong>
                <small>Check registration requirements</small>
              </button>
            </div>
          </div>
        )}

        <div className="message-list" aria-live="polite">
          {messages.map((message, index) => (
            <article
              className={`message ${message.role}`}
              key={`${message.role}-${index}`}
            >
              <span className="message-label">
                {message.role === "user" ? "You" : "Assistant"}
              </span>
              <p>{message.content}</p>

              {message.role === "assistant" && (
                <>
                  <div className={`citation-status ${message.validationStatus}`}>
                    {message.validationStatus === "verified" &&
                      "Second-pass citation check: all displayed claims passed."}
                    {message.validationStatus === "partial" &&
                      "Second-pass citation check: only supported claims are shown."}
                    {message.validationStatus === "unverified" &&
                      "Second-pass citation check could not verify an answer."}
                    {message.validationStatus === "not_applicable" &&
                      "Citation check not applicable."}
                  </div>

                  {message.warnings?.length > 0 && (
                    <div className="message-warnings" role="note">
                      <strong>Review notes</strong>
                      <ul>
                        {message.warnings.map((warning, warningIndex) => (
                          <li key={warningIndex}>{warning}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="message-sources">
                    <h4>Cited Source Chunks</h4>
                    {message.sources?.length > 0 ? (
                      <ul className="source-chunk-list">
                        {message.sources.map((source, sourceIndex) => (
                          <li key={`${source.source_id || source.filename}-${sourceIndex}`}>
                            <strong>
                              [{source.source_id || `S${sourceIndex + 1}`}] {source.filename}
                            </strong>
                            {source.chunk_index !== undefined && (
                              <span className="source-chunk-index">
                                Chunk index {source.chunk_index}
                              </span>
                            )}
                            {source.text && (
                              <details>
                                <summary>View cited text</summary>
                                <p className="source-excerpt">{source.text}</p>
                              </details>
                            )}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p>No verified source chunks were cited.</p>
                    )}
                  </div>
                </>
              )}
            </article>
          ))}

          {loading && (
            <article className="message assistant message-loading">
              <span className="message-label">Assistant</span>
              <p>Processing your question...</p>
            </article>
          )}
        </div>

        <div className="input-area">
          <textarea
            placeholder="Type your hospital-related question..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />

          <button
            onClick={handleSend}
            disabled={!question.trim() || loading}
          >
            {loading ? "Processing..." : "Send"}
          </button>
        </div>

        {error && (
          <div className="error-message">
            <strong>Error:</strong> {error}
          </div>
        )}
      </main>
        </>
      )}
      </div>
    </div>
  );
}

export default App;
