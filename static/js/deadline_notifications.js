/* F-20: opt-in browser notifications when the dashboard is open.
   No service worker or background push; localStorage deduplicates daily alerts. */
(() => {
  const toggle = document.getElementById("notification-toggle");
  const status = document.getElementById("notification-status");
  const data = document.getElementById("notification-data");
  if (!toggle || !status || !data) return;

  let payload;
  try { payload = JSON.parse(data.textContent); }
  catch { return; }
  const key = "assignment-notify-optin:" + payload.user_id;
  const today = new Date();
  const day = today.getFullYear() + "-" +
    String(today.getMonth() + 1).padStart(2, "0") + "-" +
    String(today.getDate()).padStart(2, "0");
  const enabled = () => {
    try { return localStorage.getItem(key) === "yes"; }
    catch { return false; }
  };
  const save = value => {
    try { localStorage.setItem(key, value ? "yes" : "no"); return true; }
    catch { status.textContent = "브라우저 저장소를 사용할 수 없습니다."; return false; }
  };
  const supported = () => "Notification" in window && window.isSecureContext;
  const refresh = () => {
    if (!supported()) {
      toggle.disabled = true;
      status.textContent = "이 브라우저 또는 접속 환경에서는 알림을 지원하지 않습니다. localhost 또는 HTTPS에서 사용하세요.";
      return;
    }
    if (Notification.permission === "denied") {
      toggle.disabled = true;
      status.textContent = "브라우저에서 알림이 차단되어 있습니다. 사이트 설정에서 권한을 변경하세요.";
      return;
    }
    toggle.textContent = enabled() ? "브라우저 알림 끄기" : "브라우저 알림 켜기";
    status.textContent = enabled()
      ? "알림 활성화됨 · 대시보드 접속 시 최대 하루 한 번 알림"
      : "알림 꺼짐 · 버튼을 누르면 권한을 요청합니다.";
  };
  const notify = () => {
    if (!supported() || !enabled() || Notification.permission !== "granted") return;
    for (const item of payload.alerts) {
      const dedupKey = key + ":" + day + ":" + item.id;
      try {
        if (localStorage.getItem(dedupKey)) continue;
        localStorage.setItem(dedupKey, "sent");
      } catch { continue; }
      const when = item.days < 0 ? Math.abs(item.days) + "일 지남" :
        item.days === 0 ? "오늘 마감" : item.days + "일 남음";
      try {
        new Notification("과제 마감 알림", { body: item.title + " · " + when, tag: dedupKey });
      } catch {
        try { localStorage.removeItem(dedupKey); } catch {}
      }
    }
  };
  toggle.addEventListener("click", async () => {
    if (enabled()) {
      save(false);
      refresh();
      return;
    }
    if (!supported()) { refresh(); return; }
    let permission = Notification.permission;
    if (permission === "default") {
      try { permission = await Notification.requestPermission(); }
      catch { status.textContent = "알림 권한 요청에 실패했습니다."; return; }
    }
    if (permission !== "granted") { refresh(); return; }
    if (save(true)) {
      refresh();
      notify();
    }
  });
  refresh();
  notify();
})();
