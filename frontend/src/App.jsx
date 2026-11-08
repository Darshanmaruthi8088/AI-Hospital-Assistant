import { useState, useEffect } from "react";
import "./App.css";

function App() {
  const [question, setQuestion] = useState("");
  const [activePage, setActivePage] = useState("dashboard");
  const [patients, setPatients] = useState([]);
  const [patientsLoading, setPatientsLoading] = useState(false);
  const [patientError, setPatientError] = useState("");
  const [patientSearch, setPatientSearch] = useState("");

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

          <button className="sidebar-link" disabled>
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
            {activePage === "dashboard" ? "Dashboard" : "Chat Assistant"}
          </h1>
          <p>
            {activePage === "dashboard"
              ? "Hospital information and system overview"
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
