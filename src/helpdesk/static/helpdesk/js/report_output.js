(() => {
  'use strict'

  const ctx = document.getElementById('myChart')
  const data = JSON.parse(document.getElementById('chartData').textContent)
  const params = new URLSearchParams(window.location.search)
  console.info(`params:${params}`)

  const options = {
    responsive: true,
    maintainAspectRatio: true,
    indexAxis: params.get('indexAxis') || 'x',
    elements: {
      bar: {
        borderWidth: 2
      }
    },
    scales: {
      x: {
        stacked: false,
        grid: {
          display: false
        }
      },
      y: {
        stacked: false,
        beginAtZero: true,
        title: {
          display: true,
          padding: {
            bottom: 30
          },
          text: data.y_label
        }
      }
    },
    interaction: {
      mode: 'nearest',
      intersect: false
    }
  }

  new Chart(ctx, { type: data.charttype, data, options })
})()
