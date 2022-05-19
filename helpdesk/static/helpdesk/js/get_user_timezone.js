 var timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
 now = new Date()
 $.ajax({
    url: "helpdesk/set_user_timezone/",
    action: "GET",
    data: {
      timezone: timezone,
    },
    success: function (data) {
      if (data.status) {
        location.reload();
      }
    }
 })
