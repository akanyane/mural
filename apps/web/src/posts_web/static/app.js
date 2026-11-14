// Pequenos comportamentos de interface que não valem um framework.
(function () {
  const root = document.documentElement;
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const currentTheme = () => root.dataset.theme || (prefersDark.matches ? "dark" : "light");

  // Alternar tema claro/escuro (com transição onde houver View Transitions).
  document.addEventListener("click", (event) => {
    if (!event.target.closest("[data-theme-toggle]")) return;
    const next = currentTheme() === "dark" ? "light" : "dark";
    const apply = () => {
      root.dataset.theme = next;
      try {
        localStorage.setItem("theme", next);
      } catch (_) {
        /* armazenamento indisponível: o tema vale só para esta página */
      }
    };
    if (document.startViewTransition && !reducedMotion.matches) {
      document.startViewTransition(apply);
    } else {
      apply();
    }
  });

  // Ctrl/Cmd + Enter num textarea envia o formulário (publicar/comentar/salvar).
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || !(event.ctrlKey || event.metaKey)) return;
    const field = event.target;
    if (field instanceof HTMLTextAreaElement && field.form) {
      event.preventDefault();
      field.form.requestSubmit();
    }
  });

  // Botão de comentários: o primeiro clique carrega o painel via HTMX,
  // o segundo fecha (sem nova requisição).
  document.addEventListener("htmx:beforeRequest", (event) => {
    const button = event.detail.elt;
    if (!button.matches || !button.matches("[data-comments-toggle]")) return;
    if (button.getAttribute("aria-expanded") === "true") {
      event.preventDefault();
      document.getElementById(button.getAttribute("aria-controls")).replaceChildren();
      button.setAttribute("aria-expanded", "false");
    }
  });

  document.addEventListener("htmx:afterRequest", (event) => {
    const button = event.detail.elt;
    if (!button.matches || !button.matches("[data-comments-toggle]")) return;
    if (event.detail.successful) {
      button.setAttribute("aria-expanded", "true");
      const field = document.querySelector(`#${button.getAttribute("aria-controls")} textarea`);
      if (field) field.focus({ preventScroll: true });
    }
  });
})();
