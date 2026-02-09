/* ========================================
   AI Face Recognition Attendance System
   Enhanced JavaScript File
   ======================================== */

// Global State
let isAttendanceRunning = false;
let facesDetectedCount = 0;
let studentsMarkedCount = 0;
let currentTheme = "dark";

// DOM Content Loaded
document.addEventListener("DOMContentLoaded", function () {
  initializeAnimations();
  initializeFormValidation();
  initializeDashboard();
  initializeTheme();
  initializeSearch();
  updateSessionDate();
});

/* ========================================
   Theme Toggle
   ======================================== */
function initializeTheme() {
  const savedTheme = localStorage.getItem("theme") || "dark";
  setTheme(savedTheme);
}

function toggleTheme() {
  currentTheme = currentTheme === "dark" ? "light" : "dark";
  setTheme(currentTheme);
  localStorage.setItem("theme", currentTheme);
}

function setTheme(theme) {
  currentTheme = theme;
  document.body.classList.remove("theme-dark", "theme-light");
  document.body.classList.add(`theme-${theme}`);

  const themeIcon = document.querySelector(".theme-icon");
  if (themeIcon) {
    themeIcon.textContent = theme === "dark" ? "🌙" : "☀️";
  }
}

/* ========================================
   Page Load Animations
   ======================================== */
function initializeAnimations() {
  const animatedElements = document.querySelectorAll(".fade-in, .slide-up");

  animatedElements.forEach((el, index) => {
    el.style.opacity = "0";
    setTimeout(
      () => {
        el.style.opacity = "1";
      },
      100 * (index + 1),
    );
  });

  const observerOptions = {
    threshold: 0.1,
    rootMargin: "0px 0px -50px 0px",
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
      }
    });
  }, observerOptions);

  document
    .querySelectorAll(".card, .stat-card, .panel-section")
    .forEach((el) => {
      observer.observe(el);
    });
}

/* ========================================
   Form Validation
   ======================================== */
function initializeFormValidation() {
  const forms = document.querySelectorAll("form");

  forms.forEach((form) => {
    const inputs = form.querySelectorAll(".form-input");

    inputs.forEach((input) => {
      input.addEventListener("focus", function () {
        this.parentElement.classList.add("focused");
      });

      input.addEventListener("blur", function () {
        this.parentElement.classList.remove("focused");
        validateInput(this);
      });

      input.addEventListener("input", function () {
        if (this.classList.contains("error")) {
          validateInput(this);
        }
      });
    });

    form.addEventListener("submit", function (e) {
      let isValid = true;

      inputs.forEach((input) => {
        if (!validateInput(input)) {
          isValid = false;
        }
      });

      if (!isValid) {
        e.preventDefault();
        showNotification("Please fill in all required fields", "error");
      }
    });
  });
}

function validateInput(input) {
  const value = input.value.trim();
  const isRequired = input.hasAttribute("required");

  if (isRequired && !value) {
    input.classList.add("error");
    return false;
  }

  input.classList.remove("error");
  return true;
}

/* ========================================
   Dashboard Functions
   ======================================== */
function initializeDashboard() {
  const startBtn = document.getElementById("startAttendance");
  const stopBtn = document.getElementById("stopAttendance");

  if (startBtn && stopBtn) {
    startBtn.addEventListener("click", startAttendance);
    stopBtn.addEventListener("click", stopAttendance);
  }

  loadAttendanceData();
  updateCurrentTime();
  setInterval(updateCurrentTime, 1000);

  // Initialize log timestamp
  updateLogTimestamp();
}

function updateSessionDate() {
  const sessionDateEl = document.getElementById("sessionDate");
  const currentDateEl = document.getElementById("currentDate");

  const now = new Date();
  const dateStr = now.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  if (sessionDateEl) sessionDateEl.textContent = dateStr;
  if (currentDateEl) currentDateEl.textContent = dateStr;
}

/* ========================================
   Attendance Control Functions
   ======================================== */
function startAttendance() {
  const startBtn = document.getElementById("startAttendance");
  const stopBtn = document.getElementById("stopAttendance");
  const resetBtn = document.getElementById("resetSession");

  startBtn.disabled = true;
  startBtn.innerHTML = '<span class="btn-icon">⏳</span> Starting...';

  // Call backend API to start attendance session
  fetch("/api/start_attendance", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      subject: document.getElementById('sessionSubject')?.textContent || 'General',
      section: 'A',
      period: '1'
    })
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success || data.message) {
        isAttendanceRunning = true;

        // Update status indicator
        updateStatusIndicator(true);

        // Update session status badge
        updateSessionBadge(true);

        // Update camera status
        updateCameraStatus(true);

        // Update button states
        startBtn.disabled = true;
        startBtn.innerHTML = '<span class="btn-icon">▶️</span> Start Attendance';
        stopBtn.disabled = false;
        if (resetBtn) resetBtn.disabled = true;

        // Activate webcam container
        const webcamContainer = document.querySelector(".webcam-container");
        if (webcamContainer) {
          webcamContainer.classList.add("active");
        }

        // Hide placeholder and show camera feed
        const placeholder = document.querySelector(".webcam-placeholder");
        const webcamFeed = document.getElementById("webcamFeed");

        if (placeholder) placeholder.style.display = "none";
        if (webcamFeed) {
          webcamFeed.src = "/video_feed";
          webcamFeed.style.display = "block";
        }

        // Add log entry
        addLogEntry("Attendance session started - Camera active", "success");

        showNotification("Attendance started successfully!", "success");

        // Start polling for recognized faces
        startRecognitionPolling();
      } else {
        throw new Error(data.error || "Failed to start attendance");
      }
    })
    .catch((error) => {
      console.error("Error starting attendance:", error);
      startBtn.disabled = false;
      startBtn.innerHTML = '<span class="btn-icon">▶️</span> Start Attendance';
      showNotification("Failed to start attendance: " + error.message, "error");
    });
}

// Poll for recognized faces from backend
let recognitionPollingInterval = null;

function startRecognitionPolling() {
  if (recognitionPollingInterval) clearInterval(recognitionPollingInterval);

  recognitionPollingInterval = setInterval(() => {
    if (!isAttendanceRunning) {
      clearInterval(recognitionPollingInterval);
      return;
    }

    // Fetch current attendance data
    loadAttendanceData();
  }, 2000); // Poll every 2 seconds
}

function stopAttendance() {
  const startBtn = document.getElementById("startAttendance");
  const stopBtn = document.getElementById("stopAttendance");
  const resetBtn = document.getElementById("resetSession");

  stopBtn.disabled = true;
  stopBtn.innerHTML = '<span class="btn-icon">⏳</span> Stopping...';

  // Stop polling
  if (recognitionPollingInterval) {
    clearInterval(recognitionPollingInterval);
    recognitionPollingInterval = null;
  }

  // Call backend API to stop attendance
  fetch("/api/stop_attendance", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })
    .then((response) => response.json())
    .then((data) => {
      isAttendanceRunning = false;

      // Update status indicator
      updateStatusIndicator(false);

      // Update session status badge
      updateSessionBadge(false);

      // Update camera status
      updateCameraStatus(false);

      // Update button states
      stopBtn.disabled = true;
      stopBtn.innerHTML = '<span class="btn-icon">⏹️</span> Stop Attendance';
      startBtn.disabled = false;
      if (resetBtn) resetBtn.disabled = false;

      // Deactivate webcam container
      const webcamContainer = document.querySelector(".webcam-container");
      if (webcamContainer) {
        webcamContainer.classList.remove("active");
      }

      // Hide camera feed and show placeholder
      const placeholder = document.querySelector(".webcam-placeholder");
      const webcamFeed = document.getElementById("webcamFeed");

      if (webcamFeed) {
        webcamFeed.src = "";
        webcamFeed.style.display = "none";
      }
      if (placeholder) placeholder.style.display = "flex";

      // Add log entry
      addLogEntry("Attendance session stopped - Camera deactivated", "info");

      showNotification("Attendance stopped successfully!", "info");
    })
    .catch((error) => {
      console.error("Error stopping attendance:", error);
      // Still update UI even if API fails
      isAttendanceRunning = false;
      stopBtn.disabled = true;
      stopBtn.innerHTML = '<span class="btn-icon">⏹️</span> Stop Attendance';
      startBtn.disabled = false;
      showNotification("Attendance stopped", "info");
    });
}

function resetSession() {
  if (
    !confirm(
      "Are you sure you want to reset this session? All attendance data will be cleared.",
    )
  ) {
    return;
  }

  facesDetectedCount = 0;
  studentsMarkedCount = 0;

  updateFacesDetected(0);
  updateStudentsMarked(0);

  // Clear attendance table
  const tableBody = document.getElementById("attendanceData");
  if (tableBody) {
    tableBody.innerHTML = "";
  }

  // Update badge
  const badge = document.getElementById("attendanceCountBadge");
  if (badge) {
    badge.textContent = "0 marked";
  }

  // Show empty state
  const emptyState = document.getElementById("emptyState");
  if (emptyState) {
    emptyState.classList.add("visible");
  }

  // Clear logs
  clearLogs();

  addLogEntry("Session reset successfully", "warning");
  showNotification("Session has been reset", "warning");
}

/* ========================================
   Status Update Functions
   ======================================== */
function updateStatusIndicator(isRunning) {
  const statusDot = document.querySelector(".status-dot");
  const statusTitle = document.querySelector(".status-text h4");
  const statusDesc = document.querySelector(".status-text p");

  if (statusDot) {
    statusDot.classList.remove("running", "stopped");
    statusDot.classList.add(isRunning ? "running" : "stopped");
  }

  if (statusTitle) {
    statusTitle.textContent = isRunning
      ? "Attendance Running"
      : "Attendance Stopped";
  }

  if (statusDesc) {
    statusDesc.textContent = isRunning
      ? "Face recognition is actively scanning..."
      : 'Click "Start Attendance" to begin face recognition';
  }
}

function updateSessionBadge(isRunning) {
  const badge = document.getElementById("sessionStatusBadge");
  if (badge) {
    badge.classList.remove("running", "stopped");
    badge.classList.add(isRunning ? "running" : "stopped");
    badge.innerHTML = `<span class="status-dot-mini"></span>${isRunning ? "Running" : "Stopped"}`;
  }
}

function updateCameraStatus(isActive) {
  const statusEl = document.getElementById("cameraStatus");
  const iconEl = document.getElementById("cameraStatusIcon");

  if (statusEl) {
    statusEl.textContent = isActive ? "Active" : "Inactive";
    statusEl.className = isActive ? "status-active" : "status-inactive";
  }

  if (iconEl) {
    iconEl.classList.toggle("active", isActive);
  }
}

function updateFacesDetected(count) {
  const el = document.getElementById("facesDetected");
  if (el) {
    el.textContent = count;
    el.classList.add("live-count");
  }
}

function updateStudentsMarked(count) {
  const el = document.getElementById("studentsMarked");
  if (el) {
    el.textContent = count;
  }

  const badge = document.getElementById("attendanceCountBadge");
  if (badge) {
    badge.textContent = `${count} marked`;
  }
}

/* ========================================
   Face Detection Simulation
   ======================================== */
function startFaceDetectionSimulation() {
  if (!isAttendanceRunning) return;

  // Simulate random face detection every 3-7 seconds
  const delay = 3000 + Math.random() * 4000;

  setTimeout(() => {
    if (isAttendanceRunning) {
      // Random faces detected
      facesDetectedCount = Math.floor(Math.random() * 3) + 1;
      updateFacesDetected(facesDetectedCount);

      // Continue simulation
      startFaceDetectionSimulation();
    }
  }, delay);
}

/* ========================================
   Attendance Data Functions - Two Column Layout
   ======================================== */
function loadAttendanceData() {
  const presentBody = document.getElementById("presentData");
  const absentBody = document.getElementById("absentData");
  const totalStudentsEl = document.getElementById("totalStudents");

  if (!presentBody && !absentBody) return;

  // Fetch attendance data from backend API
  fetch("/api/attendance_data")
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        // Update total students count
        if (totalStudentsEl) {
          totalStudentsEl.textContent = data.total;
        }

        // Store in global for later use
        window.attendanceData = {
          present: data.present,
          absent: data.absent,
          total: data.total,
        };

        renderPresentTable(data.present);
        renderAbsentTable(data.absent);

        studentsMarkedCount = data.present_count;
        updateStudentsMarked(studentsMarkedCount);
      }
    })
    .catch((error) => {
      console.error("Error loading attendance data:", error);
      // Fallback to empty state
      renderPresentTable([]);
      renderAbsentTable([]);
    });
}

function renderPresentTable(data) {
  const tableBody = document.getElementById("presentData");
  const emptyState = document.getElementById("presentEmptyState");
  const badge = document.getElementById("presentCountBadge");

  if (!tableBody) return;

  // Update badge
  if (badge) {
    badge.textContent = data.length;
  }

  // Show/hide empty state
  if (emptyState) {
    if (data.length > 0) {
      emptyState.style.display = "none";
    } else {
      emptyState.style.display = "block";
    }
  }

  tableBody.innerHTML = "";

  data.forEach((student, index) => {
    const row = document.createElement("tr");
    row.style.animationDelay = `${index * 0.05}s`;
    row.classList.add("fade-in");
    row.dataset.studentId = student.id;

    const initials = student.name
      .split(" ")
      .map((n) => n[0])
      .join("");
    const confidenceHtml =
      student.confidence > 0
        ? `<span class="confidence-badge">${student.confidence}%</span>`
        : '<span class="confidence-badge low">--</span>';

    row.innerHTML = `
            <td>
                <div class="student-info">
                    <div class="student-avatar">${initials}</div>
                    <div>
                        <div class="student-name">${student.name}</div>
                    </div>
                </div>
            </td>
            <td class="student-id">${student.id}</td>
            <td>${student.time || "--:--"}</td>
            <td>${confidenceHtml}</td>
            <td>
                <button class="btn btn-sm btn-danger" onclick="markStudentAbsent('${student.id}', '${student.name}')">
                    <span class="btn-icon">✗</span> Mark Absent
                </button>
            </td>
        `;

    tableBody.appendChild(row);
  });
}

function renderAbsentTable(data) {
  const tableBody = document.getElementById("absentData");
  const emptyState = document.getElementById("absentEmptyState");
  const badge = document.getElementById("absentCountBadge");

  if (!tableBody) return;

  // Update badge
  if (badge) {
    badge.textContent = data.length;
  }

  // Show/hide empty state
  if (emptyState) {
    if (data.length > 0) {
      emptyState.style.display = "none";
    } else {
      emptyState.style.display = "block";
    }
  }

  tableBody.innerHTML = "";

  data.forEach((student, index) => {
    const row = document.createElement("tr");
    row.style.animationDelay = `${index * 0.05}s`;
    row.classList.add("fade-in");
    row.dataset.studentId = student.id;

    const initials = student.name
      .split(" ")
      .map((n) => n[0])
      .join("");

    row.innerHTML = `
            <td>
                <div class="student-info">
                    <div class="student-avatar" style="background: linear-gradient(135deg, #fc8181, #f56565);">${initials}</div>
                    <div>
                        <div class="student-name">${student.name}</div>
                    </div>
                </div>
            </td>
            <td class="student-id">${student.id}</td>
            <td>
                <button class="btn-mark-present" onclick="markStudentPresent('${student.id}', '${student.name}')">
                    ✓ Mark Present
                </button>
            </td>
        `;

    tableBody.appendChild(row);
  });
}

function markStudentPresent(studentId, studentName) {
  if (!window.attendanceData) return;

  const now = new Date();
  const timeStr = now.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
  const confidence = (95 + Math.random() * 5).toFixed(1);

  // Add to present list
  const newPresentStudent = {
    id: studentId,
    name: studentName,
    time: timeStr,
    confidence: parseFloat(confidence),
  };
  window.attendanceData.present.push(newPresentStudent);

  // Remove from absent list
  window.attendanceData.absent = window.attendanceData.absent.filter(
    (s) => s.id !== studentId,
  );

  // Re-render both tables
  renderPresentTable(window.attendanceData.present);
  renderAbsentTable(window.attendanceData.absent);

  // Update counts
  studentsMarkedCount = window.attendanceData.present.length;
  updateStudentsMarked(studentsMarkedCount);

  // Log and notify
  addLogEntry(`${studentName} manually marked present`, "success");
  showNotification(`${studentName} marked present!`, "success");
}

function markStudentAbsent(studentId, studentName) {
  if (!window.attendanceData) return;

  // Remove from present list
  window.attendanceData.present = window.attendanceData.present.filter(
    (s) => s.id !== studentId,
  );

  // Add to absent list
  const absentStudent = {
    id: studentId,
    name: studentName,
  };
  window.attendanceData.absent.push(absentStudent);

  // Re-render both tables
  renderPresentTable(window.attendanceData.present);
  renderAbsentTable(window.attendanceData.absent);

  // Update counts
  studentsMarkedCount = window.attendanceData.present.length;
  updateStudentsMarked(studentsMarkedCount);

  // Log and notify
  addLogEntry(`${studentName} marked absent`, "warning");
  showNotification(`${studentName} marked absent!`, "warning");
}

function markAllPresent() {
  if (!window.attendanceData) return;

  const now = new Date();
  const timeStr = now.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });

  // Mark all absent students as present
  window.attendanceData.absent.forEach((student) => {
    const confidence = (95 + Math.random() * 5).toFixed(1);
    window.attendanceData.present.push({
      id: student.id,
      name: student.name,
      time: timeStr,
      confidence: parseFloat(confidence),
    });
  });

  const markedCount = window.attendanceData.absent.length;
  window.attendanceData.absent = [];

  // Re-render both tables
  renderPresentTable(window.attendanceData.present);
  renderAbsentTable(window.attendanceData.absent);

  // Update counts
  studentsMarkedCount = window.attendanceData.present.length;
  updateStudentsMarked(studentsMarkedCount);

  addLogEntry(`Marked ${markedCount} students as present`, "success");
  showNotification(
    `All ${markedCount} absent students marked present!`,
    "success",
  );
}

/* ========================================
   Activity Log Functions
   ======================================== */
function addLogEntry(message, type = "info") {
  const logsContainer = document.getElementById("activityLogs");
  if (!logsContainer) return;

  const now = new Date();
  const timeStr = now.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  const icons = {
    success: "✓",
    error: "✗",
    warning: "⚠️",
    info: "ℹ️",
  };

  const logItem = document.createElement("div");
  logItem.className = `log-item ${type} fade-in`;
  logItem.innerHTML = `
        <span class="log-time">${timeStr}</span>
        <span class="log-icon">${icons[type]}</span>
        <span class="log-message">${message}</span>
    `;

  // Insert at the top
  logsContainer.insertBefore(logItem, logsContainer.firstChild);

  // Limit to 50 entries
  while (logsContainer.children.length > 50) {
    logsContainer.removeChild(logsContainer.lastChild);
  }
}

function clearLogs() {
  const logsContainer = document.getElementById("activityLogs");
  if (logsContainer) {
    logsContainer.innerHTML = "";
    addLogEntry("Logs cleared", "info");
  }
}

function updateLogTimestamp() {
  const firstLog = document.querySelector(".log-item .log-time");
  if (firstLog && firstLog.textContent === "--:--:--") {
    const now = new Date();
    firstLog.textContent = now.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  }
}

/* ========================================
   Search Functionality - Two Column Layout
   ======================================== */
function initializeSearch() {
  // Search for Present table
  const searchPresent = document.getElementById("searchPresent");
  if (searchPresent) {
    searchPresent.addEventListener("input", function () {
      const query = this.value.toLowerCase().trim();
      const rows = document.querySelectorAll("#presentData tr");
      filterTableRows(rows, query);
    });
  }

  // Search for Absent table
  const searchAbsent = document.getElementById("searchAbsent");
  if (searchAbsent) {
    searchAbsent.addEventListener("input", function () {
      const query = this.value.toLowerCase().trim();
      const rows = document.querySelectorAll("#absentData tr");
      filterTableRows(rows, query);
    });
  }
}

function filterTableRows(rows, query) {
  rows.forEach((row) => {
    const name = row.querySelector(".student-name");
    const id = row.querySelector(".student-id");

    if (name && id) {
      const matches =
        name.textContent.toLowerCase().includes(query) ||
        id.textContent.toLowerCase().includes(query);
      row.style.display = matches ? "" : "none";
    }
  });
}

/* ========================================
   Export Functionality
   ======================================== */
function exportAttendance() {
  // Use backend Excel export API
  showNotification("Generating Excel report...", "info");

  // Trigger download by navigating to export endpoint
  window.location.href = "/api/export_excel";

  addLogEntry("Attendance exported to Excel", "success");
  showNotification("Attendance exported successfully!", "success");
}

/* ========================================
   Utility Functions
   ======================================== */
function formatDate(dateString) {
  const options = { year: "numeric", month: "short", day: "numeric" };
  return new Date(dateString).toLocaleDateString("en-US", options);
}

function capitalizeFirst(string) {
  return string.charAt(0).toUpperCase() + string.slice(1);
}

function updateCurrentTime() {
  const timeElement = document.getElementById("currentTime");
  if (timeElement) {
    const now = new Date();
    timeElement.textContent = now.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }
}

/* ========================================
   Notification System
   ======================================== */
function showNotification(message, type = "info") {
  const existingNotification = document.querySelector(".notification");
  if (existingNotification) {
    existingNotification.remove();
  }

  const notification = document.createElement("div");
  notification.className = `notification notification-${type}`;

  const icons = {
    success: "✓",
    error: "✗",
    warning: "⚠",
    info: "ℹ",
  };

  notification.innerHTML = `
        <span class="notification-icon">${icons[type]}</span>
        <span class="notification-message">${message}</span>
        <button class="notification-close" onclick="this.parentElement.remove()">×</button>
    `;

  notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        gap: 12px;
        z-index: 9999;
        animation: slideInRight 0.3s ease forwards;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        font-weight: 500;
    `;

  const colors = {
    success: { bg: "rgba(72, 187, 120, 0.95)", color: "#fff" },
    error: { bg: "rgba(252, 129, 129, 0.95)", color: "#fff" },
    warning: { bg: "rgba(246, 173, 85, 0.95)", color: "#1a1a2e" },
    info: { bg: "rgba(99, 179, 237, 0.95)", color: "#fff" },
  };

  notification.style.background = colors[type].bg;
  notification.style.color = colors[type].color;

  const style = document.createElement("style");
  style.textContent = `
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .notification-close {
            background: none;
            border: none;
            color: inherit;
            font-size: 1.5rem;
            cursor: pointer;
            opacity: 0.7;
            transition: opacity 0.2s;
        }
        .notification-close:hover { opacity: 1; }
        .confidence-badge {
            padding: 4px 10px;
            background: rgba(72, 187, 120, 0.15);
            color: #48bb78;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        .confidence-badge.low {
            background: rgba(113, 128, 150, 0.15);
            color: #718096;
        }
    `;
  document.head.appendChild(style);

  document.body.appendChild(notification);

  setTimeout(() => {
    if (notification.parentElement) {
      notification.style.animation = "slideInRight 0.3s ease reverse forwards";
      setTimeout(() => notification.remove(), 300);
    }
  }, 4000);
}

/* ========================================
   Navigation Functions
   ======================================== */
function navigateTo(url) {
  window.location.href = url;
}

function logout() {
  if (confirm("Are you sure you want to logout?")) {
    showNotification("Logging out...", "info");

    setTimeout(() => {
      window.location.href = "/";
    }, 1000);
  }
}

/* ========================================
   Demo Mode Functions
   ======================================== */
function simulateRecognition() {
  if (!window.attendanceData) return;

  // Pick a random absent student to mark present
  if (window.attendanceData.absent.length === 0) {
    showNotification("All students are already marked present!", "info");
    return;
  }

  const randomIndex = Math.floor(
    Math.random() * window.attendanceData.absent.length,
  );
  const student = window.attendanceData.absent[randomIndex];
  const confidence = (95 + Math.random() * 5).toFixed(1);
  const now = new Date();
  const timeStr = now.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });

  // Add to recognition feed
  const recognitionFeed = document.getElementById("recognitionFeed");
  if (recognitionFeed) {
    const item = document.createElement("div");
    item.className = "recognition-item success fade-in";
    item.innerHTML = `
            <span class="recognition-icon">✓</span>
            <span class="recognition-text"><strong>${student.name}</strong> recognized (${confidence}%)</span>
        `;
    recognitionFeed.insertBefore(item, recognitionFeed.firstChild);

    // Limit items
    while (recognitionFeed.children.length > 5) {
      recognitionFeed.removeChild(recognitionFeed.lastChild);
    }
  }

  // Add log entry
  addLogEntry(
    `${student.name} marked present (${confidence}% confidence)`,
    "success",
  );

  // Move student from absent to present
  markStudentPresent(student.id, student.name);
}

/* ========================================
   Student Dashboard Functions
   ======================================== */
function markAllRead() {
  const notifications = document.querySelectorAll(".notification-item.unread");
  notifications.forEach((notif) => {
    notif.classList.remove("unread");
    notif.classList.add("read");
  });

  const badge = document.getElementById("notificationCount");
  if (badge) {
    badge.textContent = "0";
    badge.style.display = "none";
  }

  showNotification("All notifications marked as read", "success");
}

/* ========================================
   Monthly Calendar Functions
   ======================================== */
let currentCalendarDate = new Date();

// Sample attendance data for calendar (in real app, fetch from server)
const attendanceData = {
  "2026-01-24": "present",
  "2026-01-25": "absent",
  "2026-01-26": "present",
  "2026-01-27": "present",
  "2026-01-28": "present",
  "2026-01-22": "present",
  "2026-01-21": "present",
  "2026-01-20": "present",
  "2026-01-17": "absent",
  "2026-01-15": "present",
  "2026-01-14": "present",
  "2026-01-13": "present",
};

// Initialize calendar on page load
document.addEventListener("DOMContentLoaded", function () {
  initializeCalendar();
});

function initializeCalendar() {
  const calendarContainer = document.getElementById("calendarDays");
  if (!calendarContainer) return;

  renderCalendar(currentCalendarDate);
}

function changeMonth(delta) {
  currentCalendarDate.setMonth(currentCalendarDate.getMonth() + delta);
  renderCalendar(currentCalendarDate);
}

function renderCalendar(date) {
  const calendarDays = document.getElementById("calendarDays");
  const monthYearLabel = document.getElementById("calendarMonthYear");

  if (!calendarDays) return;

  const year = date.getFullYear();
  const month = date.getMonth();

  // Update header
  const monthNames = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];
  if (monthYearLabel) {
    monthYearLabel.textContent = `${monthNames[month]} ${year}`;
  }

  // Calculate days
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date();

  // Clear existing days
  calendarDays.innerHTML = "";

  // Add empty cells for days before the first day of the month
  for (let i = 0; i < firstDay; i++) {
    const emptyDay = document.createElement("div");
    emptyDay.className = "calendar-day empty";
    calendarDays.appendChild(emptyDay);
  }

  // Add days of the month
  for (let day = 1; day <= daysInMonth; day++) {
    const dayEl = document.createElement("div");
    dayEl.className = "calendar-day";
    dayEl.textContent = day;

    const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const isToday =
      today.getFullYear() === year &&
      today.getMonth() === month &&
      today.getDate() === day;
    const isFuture = new Date(year, month, day) > today;

    // Determine day status
    if (isToday) {
      dayEl.classList.add("today");
    } else if (isFuture) {
      dayEl.classList.add("future");
    } else if (attendanceData[dateStr]) {
      dayEl.classList.add(attendanceData[dateStr]);
    } else {
      dayEl.classList.add("regular");
    }

    calendarDays.appendChild(dayEl);
  }
}
