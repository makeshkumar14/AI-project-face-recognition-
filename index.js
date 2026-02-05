// Auth State
let isLoggedIn = false;
let currentUser = null;

document.addEventListener('DOMContentLoaded', () => {
    checkAuthState();
    initializeNavigation();
    initializeButtons();
    initializeLogin();
    initializeParallax();
});

function checkAuthState() {
    const saved = localStorage.getItem('faceattend_user');
    if (saved) {
        currentUser = JSON.parse(saved);
        isLoggedIn = true;
        updateUIForAuth();
    } else {
        updateUIForAuth();
    }
}

function updateUIForAuth() {
    const navRegister = document.getElementById('nav-register');
    const navAttendance = document.getElementById('nav-attendance');
    const navLogin = document.getElementById('nav-login');
    const logoutBtn = document.getElementById('logout-btn');
    const displayUsername = document.getElementById('display-username');
    const displayRole = document.getElementById('display-role');
    const btnRegister = document.getElementById('btn-register');
    const btnAttendance = document.getElementById('btn-attendance');

    if (isLoggedIn) {
        // User is logged in
        navRegister?.classList.remove('protected');
        navAttendance?.classList.remove('protected');
        navLogin.querySelector('span').textContent = 'Logged In';
        navLogin.style.pointerEvents = 'none';
        navLogin.style.opacity = '0.5';
        logoutBtn.style.display = 'block';
        displayUsername.textContent = currentUser?.username || 'Admin';
        displayRole.textContent = 'Administrator';
        btnRegister?.classList.remove('protected');
        btnAttendance?.classList.remove('protected');
    } else {
        // User is not logged in
        navRegister?.classList.add('protected');
        navAttendance?.classList.add('protected');
        navLogin.querySelector('span').textContent = 'Login';
        navLogin.style.pointerEvents = 'auto';
        navLogin.style.opacity = '1';
        logoutBtn.style.display = 'none';
        displayUsername.textContent = 'Guest';
        displayRole.textContent = 'Visitor';
    }
}

function initializeNavigation() {
    const navItems = document.querySelectorAll('.nav-item');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.dataset.section;

            // Check if protected and not logged in
            if ((section === 'register' || section === 'attendance') && !isLoggedIn) {
                showNotification('Please login to access this feature', 'warning');
                openLoginModal();
                return;
            }

            // Handle login click
            if (section === 'login') {
                if (!isLoggedIn) {
                    openLoginModal();
                }
                return;
            }

            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            const pageTitle = document.getElementById('page-title');
            const currentSection = document.getElementById('current-section');

            const titles = {
                dashboard: { title: 'Dashboard', section: 'Overview' },
                register: { title: 'Register Student', section: 'New Registration' },
                attendance: { title: 'Take Attendance', section: 'Face Capture' },
                view: { title: 'View Attendance', section: 'Records' }
            };

            if (titles[section]) {
                pageTitle.textContent = titles[section].title;
                currentSection.textContent = titles[section].section;
            }

            showNotification(`Navigating to ${titles[section]?.title || section}`);
        });
    });
}

function initializeButtons() {
    const buttons = [
        { id: 'btn-register', action: 'register', msg: 'Opening student registration...', protected: true },
        { id: 'btn-attendance', action: 'attendance', msg: 'Starting face capture...', protected: true },
        { id: 'btn-view', action: 'view', msg: 'Loading attendance records...', protected: false }
    ];

    buttons.forEach(({ id, action, msg, protected: isProtected }) => {
        const btn = document.getElementById(id);
        if (btn) {
            btn.addEventListener('click', () => {
                if (isProtected && !isLoggedIn) {
                    showNotification('Please login to access this feature', 'warning');
                    openLoginModal();
                    return;
                }
                document.getElementById(`nav-${action}`)?.click();
                showNotification(msg);
            });
        }
    });

    // Logout button
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            logout();
        });
    }
}

function initializeLogin() {
    const modal = document.getElementById('login-modal');
    const closeBtn = document.getElementById('modal-close');
    const form = document.getElementById('login-form');

    closeBtn?.addEventListener('click', closeLoginModal);

    modal?.addEventListener('click', (e) => {
        if (e.target === modal) closeLoginModal();
    });

    form?.addEventListener('submit', (e) => {
        e.preventDefault();
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;

        // Demo authentication (password: admin123)
        if (password === 'admin123') {
            login(username);
        } else {
            showNotification('Invalid password. Use "admin123"', 'error');
        }
    });
}

function openLoginModal() {
    const modal = document.getElementById('login-modal');
    modal?.classList.add('show');
    document.getElementById('username')?.focus();
}

function closeLoginModal() {
    const modal = document.getElementById('login-modal');
    modal?.classList.remove('show');
    document.getElementById('login-form')?.reset();
}

function login(username) {
    currentUser = { username };
    isLoggedIn = true;
    localStorage.setItem('faceattend_user', JSON.stringify(currentUser));
    updateUIForAuth();
    closeLoginModal();
    showNotification(`Welcome back, ${username}!`, 'success');
}

function logout() {
    currentUser = null;
    isLoggedIn = false;
    localStorage.removeItem('faceattend_user');
    updateUIForAuth();
    showNotification('You have been logged out');
    document.getElementById('nav-dashboard')?.click();
}

function showNotification(message, type = 'success') {
    const existing = document.querySelector('.notification');
    if (existing) existing.remove();

    const colors = {
        success: '#4facfe',
        warning: '#ff9f43',
        error: '#f5576c'
    };

    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.innerHTML = `<div class="notification-content"><svg viewBox="0 0 24 24" fill="none" style="color: ${colors[type]}"><path d="M22 11.08V12C21.99 14.16 21.3 16.25 20.01 17.98C18.72 19.71 16.9 20.97 14.84 21.58C12.77 22.2 10.56 22.12 8.53 21.37C6.51 20.63 4.78 19.25 3.61 17.44C2.44 15.63 1.88 13.49 2.02 11.34C2.16 9.18 3 7.14 4.4 5.5C5.8 3.86 7.69 2.72 9.8 2.24C11.9 1.76 14.1 1.98 16.07 2.86" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M22 4L12 14.01L9 11.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg><span>${message}</span></div>`;
    document.body.appendChild(notification);

    requestAnimationFrame(() => notification.classList.add('show'));
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 2500);
}

function initializeParallax() {
    const orbs = document.querySelectorAll('.orb');
    document.addEventListener('mousemove', (e) => {
        const x = e.clientX / window.innerWidth - 0.5;
        const y = e.clientY / window.innerHeight - 0.5;
        orbs.forEach((orb, i) => {
            const speed = (i + 1) * 15;
            orb.style.transform = `translate(${x * speed}px, ${y * speed}px)`;
        });
    });
}

// Dynamic notification styles
const style = document.createElement('style');
style.textContent = `
.notification { position: fixed; bottom: 24px; right: 24px; background: rgba(255,255,255,0.1); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 14px 20px; z-index: 1001; transform: translateX(120%); transition: transform 0.3s ease; }
.notification.show { transform: translateX(0); }
.notification-content { display: flex; align-items: center; gap: 10px; color: white; font-weight: 500; font-size: 0.9rem; }
.notification-content svg { width: 22px; height: 22px; }
`;
document.head.appendChild(style);
