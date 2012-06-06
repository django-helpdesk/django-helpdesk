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
        return false;
    });
});
