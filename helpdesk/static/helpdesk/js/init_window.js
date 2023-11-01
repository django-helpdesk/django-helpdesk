// Toggle the sidebar
let toggled = localStorage.getItem("helpdesk.sidebar-toggled") === 'true';
if (toggled) {
    document.body.classList.add("sidebar-toggled");
    document.getElementsByClassName("sidebar")[0].classList.add("toggled");
}
localStorage.setItem("helpdesk.sidebar-toggled", toggled);

// Toggle the ticket list's filter sidebar
let queryToggle = localStorage.getItem("helpdesk.show_query") === 'true';
$('#show_query_text').toggle(!queryToggle);
$('#hide_query_text').toggle(queryToggle);
$("#query_select").toggle(queryToggle);
let resultsCol = $("#query_card").parent();
resultsCol.toggleClass('col-12', !queryToggle);
resultsCol.toggleClass('col-sm-8', queryToggle);
resultsCol.toggleClass('col-md-9', queryToggle);
resultsCol.toggleClass('col-lg-10', queryToggle);

localStorage.setItem("helpdesk.show_query", queryToggle);