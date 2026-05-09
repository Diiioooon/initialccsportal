// Toast notification
function showToast(message) {
  var toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(function() { toast.classList.remove('show'); }, 3000);
}

// Form validation helpers
function showError(inputId, message) {
  var input = document.getElementById(inputId);
  var errorSpan = document.getElementById(inputId + '-error');
  input.classList.add('invalid');
  errorSpan.textContent = message;
}
function clearErrors() {
  var inputs = document.querySelectorAll('input');
  for (var i = 0; i < inputs.length; i++) { inputs[i].classList.remove('invalid'); }
  var selects = document.querySelectorAll('select');
  for (var i = 0; i < selects.length; i++) { selects[i].classList.remove('invalid'); }
  var errors = document.querySelectorAll('.error');
  for (var i = 0; i < errors.length; i++) { errors[i].textContent = ''; }
}
function isValidEmail(email) { return email.includes('@') && email.includes('.'); }

var allInputs = document.querySelectorAll('input');
for (var i = 0; i < allInputs.length; i++) {
  allInputs[i].oninput = function() {
    this.classList.remove('invalid');
    var errorSpan = document.getElementById(this.id + '-error');
    if (errorSpan) errorSpan.textContent = '';
  };
}
var allSelects = document.querySelectorAll('select');
for (var i = 0; i < allSelects.length; i++) {
  allSelects[i].onchange = function() {
    this.classList.remove('invalid');
    var errorSpan = document.getElementById(this.id + '-error');
    if (errorSpan) errorSpan.textContent = '';
  };
}

// ---------- Theme Toggle (works for both navbar button & floating button) ----------
(function() {
  const html = document.documentElement;
  const toggleBtn = document.getElementById('theme-toggle');
  if (!toggleBtn) return;

  const savedTheme = localStorage.getItem('theme');
  if (savedTheme === 'light') {
    html.removeAttribute('data-theme');
    setToggleIcon(toggleBtn, 'light');
  } else {
    html.setAttribute('data-theme', 'dark');
    setToggleIcon(toggleBtn, 'dark');
  }

  toggleBtn.addEventListener('click', function() {
    if (html.hasAttribute('data-theme')) {
      html.removeAttribute('data-theme');
      localStorage.setItem('theme', 'light');
      setToggleIcon(toggleBtn, 'light');
    } else {
      html.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
      setToggleIcon(toggleBtn, 'dark');
    }
  });

  function setToggleIcon(btn, theme) {
    if (btn.classList.contains('theme-toggle-float')) {
      // Floating button
      btn.textContent = theme === 'dark' ? '🌙' : '☀️';
    } else {
      // Navbar button
      btn.textContent = theme === 'dark' ? '🌙' : '☀️';
    }
  }
})();

// ========== Theme ==========
function applyTheme(theme) {
  var html = document.documentElement;
  html.setAttribute('data-theme', theme);

  // Sync the settings panel toggle if it exists
  var themeCheckbox = document.getElementById('theme-checkbox');
  if (themeCheckbox) {
    themeCheckbox.checked = (theme === 'light');
  }

  // Sync old navbar toggle button if it still exists on any page
  var toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.textContent = theme === 'light' ? '🌙' : '☀️';
    toggle.title = theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode';
  }
}

(function () {
  var saved = localStorage.getItem('theme') || 'dark';
  applyTheme(saved);
})();

// ========== Settings FAB + Panel (injected into every page) ==========
document.addEventListener('DOMContentLoaded', function () {

  // -- Inject FAB button --
  var fab = document.createElement('button');
  fab.className = 'settings-fab';
  fab.id = 'settings-fab';
  fab.title = 'Settings';
  fab.innerHTML = '⚙️';
  document.body.appendChild(fab);

  // -- Inject Settings Panel --
  var panel = document.createElement('div');
  panel.className = 'settings-panel';
  panel.id = 'settings-panel';

  var currentTheme = localStorage.getItem('theme') || 'dark';
  var isLight = currentTheme === 'light';

  panel.innerHTML = `
    <div class="settings-panel-title">⚙️ Settings</div>

    <div class="settings-row">
      <div class="settings-row-label">
        <span>${isLight ? '☀️ Light Mode' : '🌙 Dark Mode'}</span>
        <span>Current appearance</span>
      </div>
      <label class="toggle-switch">
        <input type="checkbox" id="theme-checkbox" ${isLight ? 'checked' : ''}>
        <span class="toggle-slider"></span>
      </label>
    </div>

    <hr class="settings-divider">

    <div class="settings-version">CCS Sit-in System v1.0</div>
  `;

  document.body.appendChild(panel);

  // -- FAB click: open/close panel --
  fab.addEventListener('click', function (e) {
    e.stopPropagation();
    panel.classList.toggle('open');
  });

  // -- Close panel when clicking outside --
  document.addEventListener('click', function (e) {
    if (!panel.contains(e.target) && e.target !== fab) {
      panel.classList.remove('open');
    }
  });

  // -- Theme checkbox toggle --
  var themeCheckbox = document.getElementById('theme-checkbox');
  themeCheckbox.addEventListener('change', function () {
    var next = this.checked ? 'light' : 'dark';
    localStorage.setItem('theme', next);
    applyTheme(next);

    // Update label text dynamically
    var label = panel.querySelector('.settings-row-label span:first-child');
    if (label) label.textContent = next === 'light' ? '☀️ Light Mode' : '🌙 Dark Mode';
  });

  // -- Remove old navbar toggle if present (cleanup) --
  var oldToggle = document.getElementById('theme-toggle');
  if (oldToggle) oldToggle.style.display = 'none';
});

// ========== Form Validation Helpers ==========
function showError(inputId, message) {
  var input = document.getElementById(inputId);
  var errorSpan = document.getElementById(inputId + '-error');
  if (input) input.classList.add('invalid');
  if (errorSpan) errorSpan.textContent = message;
}
function clearErrors() {
  document.querySelectorAll('input, select').forEach(function (el) {
    el.classList.remove('invalid');
  });
  document.querySelectorAll('.error').forEach(function (el) {
    el.textContent = '';
  });
}
function isValidEmail(email) {
  return email.includes('@') && email.includes('.');
}

document.querySelectorAll('input').forEach(function (input) {
  input.addEventListener('input', function () {
    this.classList.remove('invalid');
    var errorSpan = document.getElementById(this.id + '-error');
    if (errorSpan) errorSpan.textContent = '';
  });
});
document.querySelectorAll('select').forEach(function (sel) {
  sel.addEventListener('change', function () {
    this.classList.remove('invalid');
    var errorSpan = document.getElementById(this.id + '-error');
    if (errorSpan) errorSpan.textContent = '';
  });
});