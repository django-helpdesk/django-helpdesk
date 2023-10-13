// Toggle the sidebar
let toggled = localStorage.getItem("helpdesk.sidebar-toggled") === 'true';
if (toggled) {
    document.body.classList.add("sidebar-toggled");
    document.getElementsByClassName("sidebar")[0].classList.add("toggled");
}
localStorage.setItem("helpdesk.sidebar-toggled", toggled);