const sidebarToggle = document.getElementById("sidebar-toggle");
const adminSidebar = document.getElementById("admin-sidebar");

if (sidebarToggle && adminSidebar) {
  sidebarToggle.addEventListener("click", () => {
    const isOpen = adminSidebar.classList.toggle("is-open");
    sidebarToggle.setAttribute("aria-expanded", String(isOpen));
    sidebarToggle.setAttribute("aria-label", isOpen ? "Close admin menu" : "Open admin menu");
  });
}
