 var timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
 $.ajax({
    url: "helpdesk/set_user_timezone/",
    action: "GET",
    data: {
      timezone: timezone,
    },
    success: function (data) {
    },
    error: function (data) {
    }
 })
