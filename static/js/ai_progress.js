/* AI request progress: animated dots, a rotating status line and the elapsed
   time while a Gemini request runs. Purely presentational — the lines describe
   what the request does in general, not live server-side steps.

   Usage: <form data-ai-progress="analysis|plan|replan"> containing a submit
   button and an empty <div class="ai-progress" hidden></div>. */
(() => {
  const MESSAGES = {
    analysis: [
      "Gemini가 공지문을 읽고 있어요",
      "제출기한과 제출물을 찾고 있어요",
      "해야 할 일을 단계별로 나누고 있어요",
      "추가 요구사항을 함께 확인하고 있어요",
      "결과 형식을 점검하고 있어요",
    ],
    plan: [
      "남은 체크리스트를 살펴보고 있어요",
      "마감일까지 남은 날짜를 세고 있어요",
      "하루치 분량으로 나누고 있어요",
      "학습 계획을 정리하고 있어요",
    ],
    replan: [
      "바뀐 내용을 확인하고 있어요",
      "직접 수정한 일정은 그대로 두고 있어요",
      "남은 일정을 다시 나누고 있어요",
    ],
  };
  const BUSY_LABEL = { analysis: "분석 중…", plan: "일정 만드는 중…", replan: "다시 계획하는 중…" };
  const START_NOTE = {
    analysis: "AI 분석을 시작했어요. 결과가 나오면 이 화면에 표시됩니다.",
    plan: "학습 계획 생성을 시작했어요. 완료되면 이 화면에 표시됩니다.",
    replan: "재계획을 시작했어요. 실패하면 기존 일정이 그대로 유지됩니다.",
  };
  const SLOW_AFTER = 45; // seconds
  const reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  const elapsedText = (s) => (s < 60 ? `${s}초` : `${Math.floor(s / 60)}분 ${s % 60}초`);

  function build(box) {
    box.innerHTML =
      '<div class="ai-progress-line" aria-hidden="true">' +
      '<span class="ai-progress-dots"><i></i><i></i><i></i></span>' +
      '<span class="ai-progress-msg"></span>' +
      '<span class="ai-progress-time"></span></div>' +
      '<p class="ai-progress-note"></p>' +
      '<p class="ai-progress-live visually-hidden" role="status" aria-live="polite"></p>';
  }

  document.querySelectorAll("form[data-ai-progress]").forEach((form) => {
    const kind = MESSAGES[form.dataset.aiProgress] ? form.dataset.aiProgress : "analysis";
    const box = form.querySelector(".ai-progress");
    const button = form.querySelector('button[type="submit"]');
    if (!box || !button) return;
    const original = button.textContent;
    let timer = null;

    function reset() {
      clearInterval(timer);
      timer = null;
      box.hidden = true;
      button.disabled = false;
      button.removeAttribute("aria-busy");
      button.textContent = original;
      form.removeAttribute("data-busy");
    }

    form.addEventListener("submit", (event) => {
      // Respect earlier handlers (validation) that cancelled the submit.
      if (event.defaultPrevented) return;
      if (form.dataset.busy) { event.preventDefault(); return; }
      form.dataset.busy = "1";
      build(box);
      const msg = box.querySelector(".ai-progress-msg");
      const time = box.querySelector(".ai-progress-time");
      const note = box.querySelector(".ai-progress-note");
      const live = box.querySelector(".ai-progress-live");
      const lines = MESSAGES[kind];
      const started = Date.now();
      let i = 0;
      msg.textContent = lines[0];
      time.textContent = "0초";
      note.textContent = "응답 시간은 자료 길이와 Gemini 서버 상태에 따라 달라요. 이 창을 닫지 말고 기다려 주세요.";
      live.textContent = START_NOTE[kind];
      box.hidden = false;
      // Disable after the browser has captured the submitter for this submit.
      setTimeout(() => {
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        button.textContent = BUSY_LABEL[kind];
      }, 0);
      let slowShown = false;
      timer = setInterval(() => {
        const s = Math.floor((Date.now() - started) / 1000);
        time.textContent = elapsedText(s);
        if (s > 0 && s % 4 === 0) {
          i = (i + 1) % lines.length;
          msg.textContent = lines[i];
        }
        if (s >= SLOW_AFTER && !slowShown) {
          slowShown = true;
          note.textContent = "평소보다 오래 걸리고 있어요. 서버가 응답하면 결과나 오류 안내가 자동으로 표시됩니다.";
          live.textContent = "응답이 평소보다 오래 걸리고 있습니다.";
          box.classList.add("is-slow");
        }
      }, 1000);
      if (reduced) box.classList.add("is-static");
    });

    // Back/forward cache: never show a stale "in progress" state.
    window.addEventListener("pageshow", (e) => { if (e.persisted) reset(); });
  });
})();
