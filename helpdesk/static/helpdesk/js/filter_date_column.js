$(() => {
    $('.columnChoice').on('click', function () {
        // Clear active class
        $('.columnChoice').parent().removeClass('active')
        const value = $(this).data('value')
        // Update hidden input
        $('#id_column').val(value)
        // Disable date range input if value is no_filter
        $('#dateRange').attr('disabled', value === 'no_filter')
        // Update text from button dropdown
        $('#filteredColumn').text($(this).text())
        // Set active class on selected
        $(this).parent().addClass('active')
    })
})
