$(document).ready(function() {
    $("#filterBuilderButton").click(function() {
        const boxName = "#filterBox" + $("#filterBuilderSelect").val();
        $(boxName).slideDown();
        return false;
    });
    $(".filterBuilderRemove").click(function() {
        const boxName = "#" + $(this).parents(".filterBox").attr('id');
        $(boxName).slideUp();
        $(boxName).find("input:text, input[type=number]").each(function() {
            $(this).val("");
        });
        $(boxName).find("input:checkbox, input:radio").each(function() {
            this.checked = false;
        });
        $(boxName).find("select").each(function() {
            this.selectedIndex = -1;
        });
        return false;
    });
});
