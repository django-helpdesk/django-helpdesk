$(document).ready(function() {
    $("tr.row_hover").mouseover(function() {
        $(this).addClass("hover");
    }).mouseout(function() {
        $(this).removeClass("hover");
    });
});
