(() => {
  'use strict'

  // Toggle the side navigation
  document.querySelector('#sidebarToggle').addEventListener('click', function (e) {
    console.info('sidebar is toggled...')
    e.preventDefault()
    document.querySelector('body').classList.toggle('sidebar-toggled')
    document.querySelector('.sidebar').classList.toggle('toggled')
  })

  // Activate tooltips for all templates
  const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
  const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))
})()
