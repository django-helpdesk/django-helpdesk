/* global Chart */
(() => {
  'use strict'

  const ctx = document.getElementById('myChart')
  const data = JSON.parse(document.getElementById('chartData').textContent)
  const options = {
    responsive: true,
    maintainAspectRatio: true,
    datalabels: { display: true },
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

  const myChart = new Chart(ctx, { type: data.charttype, data, options })

  // Download chart to image
  document.getElementById('chartToPng').addEventListener('click', () => {
    const image = myChart.toBase64Image()
    const link = document.createElement('a')
    link.href = image
    link.download = 'chart.png'
    link.click()
  })
})()
