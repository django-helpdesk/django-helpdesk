$(() => {
    $(".date-field").datepicker({dateFormat: 'yy-mm-dd'});
});
$(() => {
    $(".datetime-field").datepicker({dateFormat: 'yy-mm-dd 00:00:00'});
});
$(() => {
    // TODO: This does not work as written, need to make functional
    $(".time-field").tooltip="Time format 24hr: 00:00:00";
});