(() => {
  'use strict'

  // Toggle the side navigation
  document.querySelector('#sidebarToggle').addEventListener('click', function (e) {
    e.preventDefault()
    document.querySelector('body').classList.toggle('sidebar-toggled')
    document.querySelector('.sidebar').classList.toggle('toggled')
  })

  // Activate tooltips for all templates
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
    new bootstrap.Tooltip(el)
  })
})()
