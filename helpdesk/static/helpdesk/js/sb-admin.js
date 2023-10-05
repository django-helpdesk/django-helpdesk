(function($) {
  "use strict"; // Start of use strict

   let toggled = localStorage.getItem("helpdesk.sidebar-toggled") === 'true';
   localStorage.setItem("helpdesk.sidebar-toggled", toggled);
   $("body").toggleClass("sidebar-toggled", toggled);
   $(".sidebar").toggleClass("toggled", toggled);

  // Toggle the side navigation
  $("#sidebarToggle").click(function(e) {
    toggled = !toggled;
    e.preventDefault();
    $("body").toggleClass("sidebar-toggled", toggled);
    $(".sidebar").toggleClass("toggled", toggled);
    localStorage.setItem("helpdesk.sidebar-toggled", toggled);
  });

  // Prevent the content wrapper from scrolling when the fixed side navigation hovered over
  $('body.fixed-nav .sidebar').on('mousewheel DOMMouseScroll wheel', function(e) {
    if ($window.width() > 768) {
      var e0 = e.originalEvent,
        delta = e0.wheelDelta || -e0.detail;
      this.scrollTop += (delta < 0 ? 1 : -1) * 30;
      e.preventDefault();
    }
  });

  // Scroll to top button appear
  $(document).scroll(function() {
    var scrollDistance = $(this).scrollTop();
    if (scrollDistance > 100) {
      $('.scroll-to-top').fadeIn();
    } else {
      $('.scroll-to-top').fadeOut();
    }
  });

  // Smooth scrolling using jQuery easing
  $(document).on('click', 'a.scroll-to-top', function(event) {
    var $anchor = $(this);
    $('html, body').stop().animate({
      scrollTop: ($($anchor.attr('href')).offset().top)
    }, 1000, 'easeInOutExpo');
    event.preventDefault();
  });

})(jQuery); // End of use strict
