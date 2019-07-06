$(document).ready(function() {
    $("#filterBuilderButton").click(function() {
        var boxName = "#filterBox" + $("#filterBuilderSelect").val();
        $(boxName).slideDown();
        return false;
    });
    $(".filterBuilderRemove").click(function() {
        var boxName = "#" + $(this).parents(".filterBox").attr('id');
        $(boxName).slideUp();
        $(boxName).children("input:text").each(function() {
            $(this).val("");
        });
        $(boxName).children("input:checkbox").each(function() {
            this.checked = false;
        });
        $(boxName).children("select").each(function() {
            this.selectedIndex = -1;
        });

        var selectId = $(this).parents(".filterBox").attr('id');
        var attr = selectId.replace("filterBox", "");
        $("#filterBuilderSelect-" + attr)[0].disabled = "";

        return false;
    });
});

/**
 * Called, when filterBuilderSelect input changed - will make input div appear
 * to the user. Also disable this option in the Add filter menu
 *
 * @param {string} val name of selected filter value
 */
var onFilterChange = function(val) {
  if (val) {
    var boxName = "#filterBox" + val;
    $(boxName).slideDown();
    $(boxName)[0].style.display="block";

    $("#filterBuilderSelect-" + val)[0].disabled = "disabled";
  }
};
