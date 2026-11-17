(() => {
  const button = document.getElementById("request-recheck");
  const form = document.getElementById("ai-save-form");
  const list = document.getElementById("requirement-check-list");
  const status = document.getElementById("request-check-status");
  if (!button || !form || !list || !status) return;
  let revision = 0;
  for (const name of ["summary", "tasks", "deliverables"]) {
    form.elements[name]?.addEventListener("input", () => {
      revision++;
      status.textContent =
        "검토 내용이 바뀌었습니다. 수정한 내용으로 다시 점검해 주세요.";
    });
  }
  const requirements = document.getElementById("ai-requirements");
  requirements?.addEventListener("input", () => {
    revision++;
    status.textContent =
      "요구사항이 바뀌었습니다. 새 기준으로 다시 점검해 주세요. 내용이 자동 생성되지는 않습니다.";
  });
  button.addEventListener("click", async () => {
    const checkedRevision = revision;
    button.disabled = true;
    status.textContent =
      "수정한 내용을 점검하고 있습니다. AI 재호출 없이 개수와 길이만 검사합니다.";
    try {
      const fields = new FormData(form);
      if (requirements) {
        fields.set("requirements", requirements.value);
        form.elements.requirements.value = requirements.value;
      }
      const response = await fetch(button.dataset.checkUrl, {
        method: "POST",
        body: fields,
      });
      const data = await response.json();
      if (!response.ok)
        throw new Error(
          data.error ||
            "점검하지 못했습니다. 입력 내용과 로그인 상태를 확인하세요.",
        );
      if (revision !== checkedRevision) {
        status.textContent =
          "점검 중 내용이 다시 변경되었습니다. 다시 점검해 주세요.";
        return;
      }
      list.replaceChildren();
      for (const check of data.checks) {
        const li = document.createElement("li");
        const title = document.createElement("strong");
        const detail = document.createElement("span");
        li.className = "check-result-" + check.status;
        title.textContent =
          (check.status === "passed"
            ? "충족"
            : check.status === "unmet"
              ? "확인 필요"
              : "직접 검토") +
          " · " +
          check.label;
        detail.textContent = check.detail;
        li.append(title, detail);
        list.append(li);
      }
      status.textContent =
        "수정한 내용의 개수와 길이를 점검했습니다. 의미와 사실성은 직접 검토해 주세요.";
    } catch (error) {
      status.textContent =
        error instanceof SyntaxError
          ? "점검에 실패했습니다. 로그인 상태와 연결을 확인하세요."
          : error.message;
    } finally {
      button.disabled = false;
    }
  });
})();
