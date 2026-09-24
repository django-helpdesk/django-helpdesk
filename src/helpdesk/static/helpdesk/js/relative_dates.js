/* Shared relative date rendering for ticket lists and follow-ups. */
const tooltipDateFormatter = new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'numeric', day: 'numeric',
    hour: 'numeric', minute: 'numeric', second: 'numeric',
});

function humanizeDate(date, now = new Date()) {
    const elapsed = now.getTime() - date.getTime();
    let remaining = Math.floor(Math.abs(elapsed) / 60000);
    if (remaining === 0) return 'now';

    // Approximate months and years; the tooltip retains the exact local date.
    const units = [
        ['year', 365 * 24 * 60],
        ['month', 30 * 24 * 60],
        ['week', 7 * 24 * 60],
        ['day', 24 * 60],
        ['hour', 60],
        ['minute', 1],
    ];
    const parts = [];
    for (const [unit, minutes] of units) {
        const count = Math.floor(remaining / minutes);
        if (!count) continue;
        parts.push(`${count} ${unit}${count === 1 ? '' : 's'}`);
        remaining %= minutes;
        if (parts.length === 2) break;
    }
    const duration = parts.join(' ');
    return elapsed < 0 ? `in ${duration}` : `${duration} ago`;
}

function renderDateTime(data, type) {
    if (!data) return '';
    const date = new Date(data);
    if (Number.isNaN(date.getTime())) return '';
    if (type === 'sort' || type === 'type') return date.getTime();
    const label = humanizeDate(date);
    if (type !== 'display') return label;
    const element = document.createElement('time');
    element.className = 'small text-body-secondary';
    element.dateTime = data;
    element.title = tooltipDateFormatter.format(date);
    element.textContent = label;
    return element.outerHTML;
}

function renderRelativeDates(root = document) {
    const now = new Date();
    root.querySelectorAll('time[data-relative-date]').forEach(element => {
        const date = new Date(element.dateTime);
        if (Number.isNaN(date.getTime())) return;
        element.textContent = humanizeDate(date, now);
        element.title = tooltipDateFormatter.format(date);
    });
}
