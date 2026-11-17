(() => {
  const toggle = document.querySelector(".menu-toggle");
  function closeMenu() {
    document.body.classList.remove("menu-open");
    toggle?.setAttribute("aria-expanded", "false");
    toggle?.setAttribute("aria-label", "메뉴 열기");
  }
  toggle?.addEventListener("click", () => {
    const open = document.body.classList.toggle("menu-open");
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
    if (open) document.querySelector(".sidebar nav a")?.focus();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && document.body.classList.contains("menu-open")) {
      closeMenu();
      toggle?.focus();
    }
  });
  document
    .querySelectorAll(".sidebar a")
    .forEach((a) => a.addEventListener("click", closeMenu));
})();
