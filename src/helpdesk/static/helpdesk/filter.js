$(document).ready(function() {
    $("#filterBuilderButton").click(function() {
        const boxName = "#filterBox" + $("#filterBuilderSelect").val();
        $(boxName).slideDown();
        return false;
    });
    $(".filterBuilderRemove").click(function() {
        const boxName = "#" + $(this).parents(".filterBox").attr('id');
        $(boxName).slideUp();
        $(boxName).find("input:text").each(function() {
            $(this).val("");
        });
        $(boxName).find("input:checkbox").each(function() {
            this.checked = false;
        });
        $(boxName).find("select").each(function() {
            this.selectedIndex = -1;
        });

        let selectId = $(this).parents(".filterBox").attr('id');
        const attr = selectId.replace("filterBox", "");
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
const onFilterChange = function(val) {
  if (val) {
    const boxName = "#filterBox" + val;
    $(boxName).slideDown();
    $(boxName)[0].style.display="block";

    $("#filterBuilderSelect-" + val)[0].disabled = "disabled";
  }
};
