/* Login / register form: show-password toggle, inline validation messages,
   and a busy state that blocks double submission. Server-side validation is
   unchanged and remains the source of truth. */
(() => {
  const form = document.getElementById("auth-form");
  if (!form) return;
  const user = document.getElementById("username");
  const pass = document.getElementById("password");
  const toggle = document.getElementById("password-toggle");
  const submit = form.querySelector('button[type="submit"]');
  const isRegister = pass.getAttribute("autocomplete") === "new-password";

  toggle?.addEventListener("click", () => {
    const show = pass.type === "password";
    pass.type = show ? "text" : "password";
    toggle.textContent = show ? "숨기기" : "보기";
    toggle.setAttribute("aria-pressed", String(show));
    toggle.setAttribute("aria-label", show ? "비밀번호 숨기기" : "비밀번호 보기");
  });

  function check(input) {
    let msg = "";
    const v = input.value;
    if (input === user) {
      if (!v.trim()) msg = "아이디를 입력해 주세요.";
      else if (isRegister && !/^[a-z0-9_]{3,32}$/.test(v)) msg = "영문 소문자·숫자·밑줄(_)로 3~32자를 입력해 주세요.";
    } else if (!v) msg = "비밀번호를 입력해 주세요.";
    else if (isRegister && v.length < 10) msg = `비밀번호는 10자 이상이어야 해요. (지금 ${v.length}자)`;
    const hint = document.getElementById(input.getAttribute("aria-describedby"));
    if (!hint.dataset.base) hint.dataset.base = hint.textContent;
    hint.textContent = msg || hint.dataset.base;
    hint.classList.toggle("is-error", !!msg);
    input.setAttribute("aria-invalid", msg ? "true" : "false");
    return !msg;
  }

  [user, pass].forEach((el) => {
    el.addEventListener("blur", () => { if (el.value) check(el); });
    el.addEventListener("input", () => { if (el.getAttribute("aria-invalid") === "true") check(el); });
  });

  form.addEventListener("submit", (e) => {
    const okUser = check(user), okPass = check(pass);
    if (!okUser || !okPass) {
      e.preventDefault();
      (okUser ? pass : user).focus();
      return;
    }
    if (form.dataset.busy) { e.preventDefault(); return; }
    form.dataset.busy = "1";
    setTimeout(() => {
      submit.disabled = true;
      submit.setAttribute("aria-busy", "true");
      submit.textContent = submit.dataset.busyLabel;
    }, 0);
  });

  window.addEventListener("pageshow", (e) => {
    if (!e.persisted) return;
    delete form.dataset.busy;
    submit.disabled = false;
    submit.removeAttribute("aria-busy");
    submit.textContent = isRegister ? "회원가입" : "로그인";
  });
})();
