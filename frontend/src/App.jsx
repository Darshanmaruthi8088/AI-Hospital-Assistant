import { useState, useEffect } from "react";
import "./App.css";

function App() {
  const [question, setQuestion] = useState("");
  const [activePage, setActivePage] = useState("dashboard");
  const [patients, setPatients] = useState([]);
  const [patientsLoading, setPatientsLoading] = useState(false);
  const [patientError, setPatientError] = useState("");
  const [patientSearch, setPatientSearch] = useState("");
  const [patientStatusFilter, setPatientStatusFilter] = useState("Active");
  const [importingPatients, setImportingPatients] = useState(false);
  const [importMessage, setImportMessage] = useState("");
  const [importErrors, setImportErrors] = useState([]);
  const [showAddPatient, setShowAddPatient] = useState(false);
  const [registeringPatient, setRegisteringPatient] = useState(false);
  const [registrationMessage, setRegistrationMessage] = useState("");
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [patientDetailsLoading, setPatientDetailsLoading] = useState(false);
  const [patientDetailsError, setPatientDetailsError] = useState("");
  const [editingPatient, setEditingPatient] = useState(false);
  const [savingPatient, setSavingPatient] = useState(false);
  const [staffRecords, setStaffRecords] = useState([]);
  const [staffTotalCount, setStaffTotalCount] = useState(0);
  const [staffLoading, setStaffLoading] = useState(false);
  const [staffError, setStaffError] = useState("");
  const [staffSearch, setStaffSearch] = useState("");
  const [staffRefreshKey, setStaffRefreshKey] = useState(0);
  const [staffFormOpen, setStaffFormOpen] = useState(false);
  const [selectedStaff, setSelectedStaff] = useState(null);
  const [savingStaff, setSavingStaff] = useState(false);
  const [staffFormMessage, setStaffFormMessage] = useState("");
  const [shiftRecords, setShiftRecords] = useState([]);
  const [shiftLoading, setShiftLoading] = useState(false);
  const [shiftError, setShiftError] = useState("");
  const [shiftRefreshKey, setShiftRefreshKey] = useState(0);
  const [shiftFormOpen, setShiftFormOpen] = useState(false);
  const [selectedShift, setSelectedShift] = useState(null);
  const [savingShift, setSavingShift] = useState(false);
  const [shiftFormMessage, setShiftFormMessage] = useState("");

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

  const handleImportPatients = async (event) => {
    const file = event.target.files?.[0];

    if (!file) return;

    setImportingPatients(true);
    setImportMessage("");
    setImportErrors([]);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        "http://127.0.0.1:8000/patients/import",
        {
          method: "POST",
          body: formData,
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.detail || "Unable to import patient records."
        );
      }

      const patientsResponse = await fetch(
        "http://127.0.0.1:8000/patients"
      );

      if (!patientsResponse.ok) {
        throw new Error("Import completed, but patient list refresh failed.");
      }

      const updatedPatients = await patientsResponse.json();
      setPatients(updatedPatients);

      setImportMessage(
        `Import completed! Imported: ${result.imported ?? 0}, Skipped: ${result.skipped ?? 0}, Failed: ${result.failed ?? 0}.`
      );

      setImportErrors(result.errors || []);
    } catch (error) {
      setImportMessage(`Import failed: ${error.message}`);
    } finally {
      setImportingPatients(false);
      event.target.value = "";
    }
  };

  const filteredPatients = patients.filter((patient) => {
    const matchesStatus =
      patientStatusFilter === "All" ||
      patient.Record_Status === patientStatusFilter;

    const search = patientSearch.trim().toLowerCase();

    const matchesSearch = [
      patient.Patient_ID,
      patient.Full_Name,
      patient.Contact_Number,
      patient.Department,
    ].some((value) =>
      String(value || "").toLowerCase().includes(search)
    );

    return matchesStatus && matchesSearch;
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

  useEffect(() => {
    if (activePage !== "staff") return;

    const controller = new AbortController();
    const search = staffSearch.trim();
    let timeoutId;

    const fetchStaff = async () => {
      setStaffLoading(true);
      setStaffError("");

      try {
        const listResponse = await fetch("http://127.0.0.1:8000/staff", {
          signal: controller.signal,
        });
        const allStaff = await listResponse.json().catch(() => []);

        if (!listResponse.ok) {
          throw new Error(
            Array.isArray(allStaff.detail)
              ? allStaff.detail.map((item) => item.msg).join(", ")
              : allStaff.detail || "Failed to retrieve staff records."
          );
        }

        setStaffTotalCount(allStaff.length);

        if (!search) {
          setStaffRecords(allStaff);
          return;
        }

        const searchResponse = await fetch(
          `http://127.0.0.1:8000/staff/search?q=${encodeURIComponent(search)}`,
          { signal: controller.signal }
        );
        const matchingStaff = await searchResponse.json().catch(() => []);

        if (!searchResponse.ok) {
          throw new Error(
            Array.isArray(matchingStaff.detail)
              ? matchingStaff.detail.map((item) => item.msg).join(", ")
              : matchingStaff.detail || "Staff search failed."
          );
        }

        setStaffRecords(matchingStaff);
      } catch (err) {
        if (err.name === "AbortError") return;
        setStaffError(
          err.message === "Failed to fetch"
            ? "Cannot connect to the backend. Check whether FastAPI is running."
            : err.message
        );
      } finally {
        if (!controller.signal.aborted) setStaffLoading(false);
      }
    };

    timeoutId = window.setTimeout(fetchStaff, search ? 250 : 0);

    return () => {
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, [activePage, staffSearch, staffRefreshKey]);

  useEffect(() => {
    if (activePage !== "shifts") return;

    const controller = new AbortController();

    const fetchShifts = async () => {
      setShiftLoading(true);
      setShiftError("");

      try {
        const response = await fetch("http://127.0.0.1:8000/shifts", {
          signal: controller.signal,
        });
        const result = await response.json().catch(() => ({}));

        if (!response.ok) {
          const detail = Array.isArray(result.detail)
            ? result.detail.map((item) => item.msg).join(", ")
            : result.detail;
          throw new Error(detail || "Failed to retrieve shift records.");
        }

        if (!Array.isArray(result)) {
          throw new Error("The backend returned an invalid shift list.");
        }

        setShiftRecords(result);
      } catch (err) {
        if (err.name === "AbortError") return;
        setShiftError(
          err.message === "Failed to fetch"
            ? "Cannot connect to the backend. Check whether FastAPI is running."
            : err.message
        );
      } finally {
        if (!controller.signal.aborted) setShiftLoading(false);
      }
    };

    fetchShifts();

    return () => controller.abort();
  }, [activePage, shiftRefreshKey]);

  const handleSaveStaff = async (event) => {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const staffData = Object.fromEntries(
      [...formData.entries()].map(([key, value]) => [key, value.trim()])
    );

    if (!staffData.Full_Name) {
      setStaffFormMessage("Full Name is required.");
      return;
    }

    if (!staffData.Employment_Status) {
      setStaffFormMessage("Employment Status is required.");
      return;
    }

    staffData.Joining_Date = staffData.Joining_Date || null;
    setSavingStaff(true);
    setStaffFormMessage("");

    const isEditing = Boolean(selectedStaff);
    const endpoint = isEditing
      ? `http://127.0.0.1:8000/staff/${encodeURIComponent(selectedStaff.Staff_ID)}`
      : "http://127.0.0.1:8000/staff";

    try {
      const response = await fetch(endpoint, {
        method: isEditing ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(staffData),
      });
      const result = await response.json().catch(() => ({}));

      if (!response.ok) {
        const detail = Array.isArray(result.detail)
          ? result.detail.map((item) => item.msg).join(", ")
          : result.detail;
        throw new Error(detail || "Unable to save staff details.");
      }

      setStaffFormOpen(false);
      setSelectedStaff(null);
      setStaffFormMessage(
        isEditing
          ? `Staff record ${result.Staff_ID} updated successfully.`
          : `Staff member registered successfully. Staff ID: ${result.Staff_ID}`
      );
      setStaffRefreshKey((current) => current + 1);
    } catch (err) {
      setStaffFormMessage(
        err.message === "Failed to fetch"
          ? "Cannot connect to the backend. Check whether FastAPI is running."
          : err.message
      );
    } finally {
      setSavingStaff(false);
    }
  };

  const openNewStaffForm = () => {
    setSelectedStaff(null);
    setStaffFormMessage("");
    setStaffFormOpen(true);
  };

  const openEditStaffForm = (staffMember) => {
    setSelectedStaff(staffMember);
    setStaffFormMessage("");
    setStaffFormOpen(true);
  };

  const closeStaffForm = () => {
    setStaffFormOpen(false);
    setSelectedStaff(null);
    setStaffFormMessage("");
  };

  const handleSaveShift = async (event) => {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const shiftData = Object.fromEntries(
      [...formData.entries()].map(([key, value]) => [key, value.trim()])
    );

    if (!shiftData.Shift_Name) {
      setShiftFormMessage("Shift Name is required.");
      return;
    }

    if (!shiftData.Start_Time || !shiftData.End_Time) {
      setShiftFormMessage("Start Time and End Time are required.");
      return;
    }

    if (shiftData.Start_Time === shiftData.End_Time) {
      setShiftFormMessage("Start Time and End Time must be different.");
      return;
    }

    if (
      shiftData.Crosses_Midnight === "Yes" &&
      shiftData.End_Time >= shiftData.Start_Time
    ) {
      setShiftFormMessage(
        "For an overnight shift, End Time must be earlier than Start Time."
      );
      return;
    }

    if (
      shiftData.Crosses_Midnight === "No" &&
      shiftData.End_Time <= shiftData.Start_Time
    ) {
      setShiftFormMessage(
        "For a shift that does not cross midnight, End Time must be later than Start Time."
      );
      return;
    }

    shiftData.Description = shiftData.Description || null;
    shiftData.Shift_Status = shiftData.Shift_Status || "Active";

    setSavingShift(true);
    setShiftFormMessage("");

    const isEditing = Boolean(selectedShift);
    const endpoint = isEditing
      ? `http://127.0.0.1:8000/shifts/${encodeURIComponent(selectedShift.Shift_ID)}`
      : "http://127.0.0.1:8000/shifts";

    try {
      const response = await fetch(endpoint, {
        method: isEditing ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(shiftData),
      });
      const result = await response.json().catch(() => ({}));

      if (!response.ok) {
        const detail = Array.isArray(result.detail)
          ? result.detail.map((item) => item.msg).join(", ")
          : result.detail;
        throw new Error(detail || "Unable to save shift details.");
      }

      setShiftFormOpen(false);
      setSelectedShift(null);
      setShiftFormMessage(
        isEditing
          ? `Shift ${result.Shift_ID} updated successfully.`
          : `Shift created successfully. Shift ID: ${result.Shift_ID}`
      );
      setShiftRefreshKey((current) => current + 1);
    } catch (err) {
      setShiftFormMessage(
        err.message === "Failed to fetch"
          ? "Cannot connect to the backend. Check whether FastAPI is running."
          : err.message
      );
    } finally {
      setSavingShift(false);
    }
  };

  const openNewShiftForm = () => {
    setSelectedShift(null);
    setShiftFormMessage("");
    setShiftFormOpen(true);
  };

  const openEditShiftForm = (shift) => {
    setSelectedShift(shift);
    setShiftFormMessage("");
    setShiftFormOpen(true);
  };

  const closeShiftForm = () => {
    setShiftFormOpen(false);
    setSelectedShift(null);
    setShiftFormMessage("");
  };

  const formatShiftTime = (value) => {
    if (!value) return "—";
    const [hours, minutes, seconds] = String(value).split(":");
    return seconds && seconds !== "00"
      ? `${hours}:${minutes}:${seconds}`
      : `${hours}:${minutes}`;
  };

  const formatShiftTimeInput = (value) =>
    value ? String(value).slice(0, 8) : "";

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
          patient_id: selectedPatient?.Patient_ID || null,
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

          <button
            className={`sidebar-link ${activePage === "staff" ? "active" : ""}`}
            onClick={() => setActivePage("staff")}
          >
            <span className="sidebar-icon">♟</span> Staff Management
          </button>

          <button
            className={`sidebar-link ${activePage === "shifts" ? "active" : ""}`}
            onClick={() => setActivePage("shifts")}
          >
            <span className="sidebar-icon">◷</span> Shift Management
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
              : activePage === "staff"
                ? "Staff Management"
                : activePage === "shifts"
                  ? "Shift Management"
                  : "Chat Assistant"}
          </h1>
          <p>
            {activePage === "dashboard"
              ? "Hospital information and system overview"
              : activePage === "patients"
                ? "Manage and retrieve patient records"
              : activePage === "staff"
                ? "Register, search and update staff records"
                : activePage === "shifts"
                  ? "Create and update hospital shift definitions"
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
            <div className="patient-status-filters">
              {["Active", "Inactive", "All"].map((status) => (
                <button
                  key={status}
                  type="button"
                  className={`patient-filter-button ${
                    patientStatusFilter === status ? "active" : ""
                  }`}
                  onClick={() => setPatientStatusFilter(status)}
                >
                  {status}
                </button>
              ))}
            </div>

            <div className="patient-search">
              <input
                type="text"
                placeholder="Search by patient ID, name, contact or department..."
                value={patientSearch}
                onChange={(e) => setPatientSearch(e.target.value)}
              />
            </div>

            <div className="patient-count">
              Total Patients: <strong>
                {
                  patients.filter(
                    (patient) => patient.Record_Status !== "Inactive"
                  ).length
                }
              </strong>
            </div>

            <label className="import-patient-button">
              {importingPatients ? "Importing..." : "↑ Import from Excel"}

              <input
                type="file"
                accept=".xlsx"
                onChange={handleImportPatients}
                disabled={importingPatients}
              />
            </label>

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

          {importMessage && (
            <div className="patient-import-message">
              {importMessage}
            </div>
          )}

          {importErrors.length > 0 && (
            <div className="patient-import-errors">
              <strong>Import warnings:</strong>

              {importErrors.map((error, index) => (
                <p key={`${error.row}-${index}`}>
                  Row {error.row}: {error.patient_id || ""} — {error.error || error.message}
                </p>
              ))}
            </div>
          )}

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
                    onClick={() => setEditingPatient(!editingPatient)}
                  >
                    {editingPatient ? "Cancel Editing" : "Edit Patient"}
                  </button>

                  <button
                    type="button"
                    onClick={() => setActivePage("chat")}
                  >
                    Ask AI About This Patient
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

              {editingPatient ? (
                <form
                  className="patient-form"
                  onSubmit={handleUpdatePatient}
                >
                  <div className="patient-form-grid">
                    <label>
                      Full Name *
                      <input
                        name="Full_Name"
                        defaultValue={selectedPatient.Full_Name || ""}
                        required
                      />
                    </label>

                    <label>
                      Date of Birth
                      <input
                        type="date"
                        name="Date_of_Birth"
                        defaultValue={selectedPatient.Date_of_Birth || ""}
                      />
                    </label>

                    <label>
                      Age
                      <input
                        type="number"
                        name="Age"
                        min="0"
                        max="150"
                        defaultValue={selectedPatient.Age ?? ""}
                      />
                    </label>

                    <label>
                      Gender
                      <select
                        name="Gender"
                        defaultValue={selectedPatient.Gender || ""}
                      >
                        <option value="">Select Gender</option>
                        <option>Female</option>
                        <option>Male</option>
                        <option>Other</option>
                        <option>Prefer not to say</option>
                      </select>
                    </label>

                    <label>
                      Contact Number
                      <input
                        name="Contact_Number"
                        defaultValue={selectedPatient.Contact_Number || ""}
                      />
                    </label>

                    <label>
                      Department
                      <input
                        name="Department"
                        defaultValue={selectedPatient.Department || ""}
                      />
                    </label>

                    <label>
                      Doctor Assigned
                      <input
                        name="Doctor_Assigned"
                        defaultValue={selectedPatient.Doctor_Assigned || ""}
                      />
                    </label>

                    <label>
                      Emergency Contact Name
                      <input
                        name="Emergency_Contact_Name"
                        defaultValue={selectedPatient.Emergency_Contact_Name || ""}
                      />
                    </label>

                    <label>
                      Emergency Contact Number
                      <input
                        name="Emergency_Contact_Number"
                        defaultValue={selectedPatient.Emergency_Contact_Number || ""}
                      />
                    </label>

                    <label>
                      Registration Date
                      <input
                        type="date"
                        name="Registration_Date"
                        defaultValue={selectedPatient.Registration_Date || ""}
                      />
                    </label>

                    <label>
                      Visit Type
                      <select
                        name="Visit_Type"
                        defaultValue={selectedPatient.Visit_Type || ""}
                      >
                        <option value="">Select Visit Type</option>
                        <option>OPD</option>
                        <option>IPD</option>
                        <option>Emergency</option>
                        <option>Follow-up</option>
                      </select>
                    </label>

                    <label>
                      Record Status
                      <select
                        name="Record_Status"
                        defaultValue={selectedPatient.Record_Status || ""}
                      >
                        <option value="">Select Status</option>
                        <option>Active</option>
                        <option>Discharged</option>
                        <option>Inactive</option>
                      </select>
                    </label>

                    <label className="patient-full-width">
                      Address
                      <textarea
                        name="Address"
                        rows="2"
                        defaultValue={selectedPatient.Address || ""}
                      />
                    </label>

                    <label className="patient-full-width">
                      Notes
                      <textarea
                        name="Notes"
                        rows="2"
                        defaultValue={selectedPatient.Notes || ""}
                      />
                    </label>
                  </div>

                  <div className="patient-form-actions">
                    <button
                      type="button"
                      onClick={() => setEditingPatient(false)}
                    >
                      Cancel
                    </button>

                    <button type="submit" disabled={savingPatient}>
                      {savingPatient ? "Saving..." : "Save Changes"}
                    </button>
                  </div>
                </form>
              ) : (
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
              )}
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
      ) : activePage === "staff" ? (
        <section className="dashboard-page">
          <div className="dashboard-heading">
            <span className="dashboard-tag">HOSPITAL MANAGEMENT</span>
            <h1>Staff Management</h1>
            <p>View, search, register and update hospital staff records.</p>
          </div>

          <div className="patient-toolbar staff-toolbar">
            <div className="patient-search staff-search">
              <input
                type="search"
                aria-label="Search staff records"
                placeholder="Search by staff ID, name, role, department or contact..."
                value={staffSearch}
                onChange={(event) => setStaffSearch(event.target.value)}
              />
            </div>

            <div className="patient-count" aria-live="polite">
              Total Staff: <strong>{staffTotalCount}</strong>
              {staffSearch.trim() && (
                <span className="staff-result-count">
                  {staffRecords.length} matching
                </span>
              )}
            </div>

            <button
              type="button"
              className="staff-secondary-button"
              onClick={() => setStaffRefreshKey((current) => current + 1)}
              disabled={staffLoading}
            >
              {staffLoading ? "Refreshing..." : "Refresh"}
            </button>

            <button
              type="button"
              className="add-patient-button"
              onClick={openNewStaffForm}
            >
              + Add Staff
            </button>
          </div>

          {staffFormMessage && (
            <div
              className={
                staffFormMessage.includes("successfully")
                  ? "registration-success"
                  : "registration-error"
              }
              role="status"
            >
              {staffFormMessage}
            </div>
          )}

          {staffFormOpen && (
            <div className="patient-form-container staff-form-container">
              <div className="patient-form-heading">
                <div>
                  <h2>{selectedStaff ? "Edit Staff Member" : "Register Staff Member"}</h2>
                  <p>
                    {selectedStaff
                      ? `Staff ID: ${selectedStaff.Staff_ID}`
                      : "Enter the staff member's details below."}
                  </p>
                </div>
                <button
                  type="button"
                  className="patient-form-close"
                  onClick={closeStaffForm}
                  aria-label="Close staff form"
                >
                  ×
                </button>
              </div>

              <form
                key={selectedStaff?.Staff_ID || "new-staff"}
                className="patient-form"
                onSubmit={handleSaveStaff}
              >
                <div className="patient-form-grid">
                  <label>
                    Full Name *
                    <input
                      name="Full_Name"
                      type="text"
                      required
                      maxLength="32767"
                      defaultValue={selectedStaff?.Full_Name || ""}
                    />
                  </label>

                  <label>
                    Role
                    <select name="Role" defaultValue={selectedStaff?.Role || ""}>
                      <option value="">Select a role</option>
                      {[
                        "Doctor",
                        "Nurse",
                        "Receptionist",
                        "Lab Technician",
                        "Pharmacist",
                        "Administrator",
                        "Other",
                      ].map((role) => (
                        <option key={role} value={role}>{role}</option>
                      ))}
                    </select>
                  </label>

                  <label>
                    Department
                    <input
                      name="Department"
                      type="text"
                      maxLength="32767"
                      defaultValue={selectedStaff?.Department || ""}
                    />
                  </label>

                  <label>
                    Contact Number
                    <input
                      name="Contact_Number"
                      type="tel"
                      maxLength="32767"
                      defaultValue={selectedStaff?.Contact_Number || ""}
                    />
                  </label>

                  <label>
                    Email
                    <input
                      name="Email"
                      type="email"
                      maxLength="32767"
                      defaultValue={selectedStaff?.Email || ""}
                    />
                  </label>

                  <label>
                    Employment Status *
                    <select
                      name="Employment_Status"
                      required
                      defaultValue={selectedStaff?.Employment_Status || "Active"}
                    >
                      <option value="Active">Active</option>
                      <option value="Inactive">Inactive</option>
                      <option value="On Leave">On Leave</option>
                      <option value="Resigned">Resigned</option>
                    </select>
                  </label>

                  <label>
                    Joining Date
                    <input
                      name="Joining_Date"
                      type="date"
                      defaultValue={selectedStaff?.Joining_Date || ""}
                    />
                  </label>

                  <label className="patient-full-width">
                    Notes
                    <textarea
                      name="Notes"
                      rows="3"
                      maxLength="32767"
                      defaultValue={selectedStaff?.Notes || ""}
                    />
                  </label>
                </div>

                <div className="patient-form-actions">
                  <button type="button" onClick={closeStaffForm} disabled={savingStaff}>
                    Cancel
                  </button>
                  <button type="submit" disabled={savingStaff}>
                    {savingStaff
                      ? "Saving..."
                      : selectedStaff
                        ? "Save Changes"
                        : "Register Staff"}
                  </button>
                </div>
              </form>
            </div>
          )}

          {staffLoading && <p className="staff-loading">Loading staff records...</p>}

          {staffError && (
            <div className="registration-error" role="alert">
              <strong>Error:</strong> {staffError}
            </div>
          )}

          {!staffLoading && !staffError && (
            <div className="patient-table-container">
              <table className="patient-table staff-table">
                <thead>
                  <tr>
                    <th>Staff ID</th>
                    <th>Full Name</th>
                    <th>Role</th>
                    <th>Department</th>
                    <th>Contact Number</th>
                    <th>Email</th>
                    <th>Employment Status</th>
                    <th>Joining Date</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {staffRecords.map((staffMember) => (
                    <tr key={staffMember.Staff_ID}>
                      <td><strong>{staffMember.Staff_ID}</strong></td>
                      <td>{staffMember.Full_Name || "—"}</td>
                      <td>{staffMember.Role || "—"}</td>
                      <td>{staffMember.Department || "—"}</td>
                      <td>{staffMember.Contact_Number || "—"}</td>
                      <td>{staffMember.Email || "—"}</td>
                      <td>
                        <span
                          className={`staff-status-badge status-${String(staffMember.Employment_Status || "unknown").toLowerCase().replaceAll(" ", "-")}`}
                        >
                          {staffMember.Employment_Status || "—"}
                        </span>
                      </td>
                      <td>{staffMember.Joining_Date || "—"}</td>
                      <td>
                        <button
                          type="button"
                          className="staff-edit-button"
                          onClick={() => openEditStaffForm(staffMember)}
                          aria-label={`Edit ${staffMember.Full_Name}`}
                        >
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {staffRecords.length === 0 && (
                <div className="patient-empty-state">
                  {staffSearch.trim()
                    ? "No staff members match your search."
                    : "No staff records available yet."}
                </div>
              )}
            </div>
          )}
        </section>
      ) : activePage === "shifts" ? (
        <section className="dashboard-page">
          <div className="dashboard-heading">
            <span className="dashboard-tag">HOSPITAL MANAGEMENT</span>
            <h1>Shift Management</h1>
            <p>View and manage hospital shift definitions and schedules.</p>
          </div>

          <div className="patient-toolbar staff-toolbar shift-toolbar">
            <div className="patient-count" aria-live="polite">
              Total Shifts: <strong>{shiftRecords.length}</strong>
            </div>

            <button
              type="button"
              className="staff-secondary-button"
              onClick={() => setShiftRefreshKey((current) => current + 1)}
              disabled={shiftLoading}
            >
              {shiftLoading ? "Refreshing..." : "Refresh"}
            </button>

            <button
              type="button"
              className="add-patient-button"
              onClick={openNewShiftForm}
            >
              + Create Shift
            </button>
          </div>

          {shiftFormMessage && (
            <div
              className={
                shiftFormMessage.includes("successfully")
                  ? "registration-success"
                  : "registration-error"
              }
              role="status"
            >
              {shiftFormMessage}
            </div>
          )}

          {shiftFormOpen && (
            <div className="patient-form-container shift-form-container">
              <div className="patient-form-heading">
                <div>
                  <h2>{selectedShift ? "Edit Shift" : "Create Shift"}</h2>
                  <p>
                    {selectedShift
                      ? `Shift ID: ${selectedShift.Shift_ID}`
                      : "Enter the shift details below."}
                  </p>
                </div>
                <button
                  type="button"
                  className="patient-form-close"
                  onClick={closeShiftForm}
                  aria-label="Close shift form"
                  disabled={savingShift}
                >
                  ×
                </button>
              </div>

              <form
                key={selectedShift?.Shift_ID || "new-shift"}
                className="patient-form"
                onSubmit={handleSaveShift}
              >
                <div className="patient-form-grid">
                  {selectedShift && (
                    <label>
                      Shift ID
                      <input value={selectedShift.Shift_ID} readOnly />
                    </label>
                  )}

                  <label>
                    Shift Name *
                    <input
                      name="Shift_Name"
                      type="text"
                      required
                      maxLength="32767"
                      defaultValue={selectedShift?.Shift_Name || ""}
                    />
                  </label>

                  <label>
                    Start Time *
                    <input
                      name="Start_Time"
                      type="time"
                      step="1"
                      required
                      defaultValue={formatShiftTimeInput(selectedShift?.Start_Time)}
                    />
                  </label>

                  <label>
                    End Time *
                    <input
                      name="End_Time"
                      type="time"
                      step="1"
                      required
                      defaultValue={formatShiftTimeInput(selectedShift?.End_Time)}
                    />
                  </label>

                  <label>
                    Crosses Midnight *
                    <select
                      name="Crosses_Midnight"
                      required
                      defaultValue={selectedShift?.Crosses_Midnight || "No"}
                    >
                      <option value="No">No</option>
                      <option value="Yes">Yes</option>
                    </select>
                  </label>

                  <label>
                    Shift Status *
                    <select
                      name="Shift_Status"
                      required
                      defaultValue={selectedShift?.Shift_Status || "Active"}
                    >
                      <option value="Active">Active</option>
                      <option value="Inactive">Inactive</option>
                    </select>
                  </label>

                  <label className="patient-full-width">
                    Description
                    <textarea
                      name="Description"
                      rows="3"
                      maxLength="32767"
                      defaultValue={selectedShift?.Description || ""}
                    />
                  </label>
                </div>

                {selectedShift && (
                  <p className="shift-schedule-note">
                    If this shift has assignments, the backend will reject changes to its times or midnight setting.
                  </p>
                )}

                <div className="patient-form-actions">
                  <button
                    type="button"
                    onClick={closeShiftForm}
                    disabled={savingShift}
                  >
                    Cancel
                  </button>
                  <button type="submit" disabled={savingShift}>
                    {savingShift
                      ? "Saving..."
                      : selectedShift
                        ? "Save Changes"
                        : "Create Shift"}
                  </button>
                </div>
              </form>
            </div>
          )}

          {shiftLoading && <p className="staff-loading">Loading shifts...</p>}

          {shiftError && (
            <div className="registration-error" role="alert">
              <strong>Error:</strong> {shiftError}
            </div>
          )}

          {!shiftLoading && !shiftError && (
            <div className="patient-table-container">
              <table className="patient-table shift-table">
                <thead>
                  <tr>
                    <th>Shift ID</th>
                    <th>Shift Name</th>
                    <th>Start Time</th>
                    <th>End Time</th>
                    <th>Crosses Midnight</th>
                    <th>Description</th>
                    <th>Shift Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {shiftRecords.map((shift) => (
                    <tr key={shift.Shift_ID}>
                      <td><strong>{shift.Shift_ID}</strong></td>
                      <td>{shift.Shift_Name || "—"}</td>
                      <td>{formatShiftTime(shift.Start_Time)}</td>
                      <td>{formatShiftTime(shift.End_Time)}</td>
                      <td>{shift.Crosses_Midnight || "—"}</td>
                      <td className="shift-description-cell">
                        {shift.Description || "—"}
                      </td>
                      <td>
                        <span
                          className={`staff-status-badge status-${String(shift.Shift_Status || "unknown").toLowerCase()}`}
                        >
                          {shift.Shift_Status || "—"}
                        </span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="staff-edit-button"
                          onClick={() => openEditShiftForm(shift)}
                          aria-label={`Edit ${shift.Shift_Name}`}
                        >
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {shiftRecords.length === 0 && (
                <div className="patient-empty-state">
                  No shift records available yet.
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
