// Render ticket-list dates in the page's language and the user's timezone.
const dateLocale = document.documentElement.lang || undefined;
const relativeDateFormatter = new Intl.RelativeTimeFormat(dateLocale, {numeric: 'auto'});
const calendarDateFormatter = new Intl.DateTimeFormat(dateLocale, {
    dateStyle: 'medium',
});
const tooltipDateFormatter = new Intl.DateTimeFormat(dateLocale, {
    dateStyle: 'medium',
    timeStyle: 'short',
});

function humanizeDate(date, now = new Date()) {
    const seconds = (date.getTime() - now.getTime()) / 1000;

    const units = [
        ['year', 365 * 24 * 60 * 60],
        ['month', 30 * 24 * 60 * 60],
        ['week', 7 * 24 * 60 * 60],
        ['day', 24 * 60 * 60],
        ['hour', 60 * 60],
        ['minute', 60],
        ['second', 1],
    ];
    for (const [unit, duration] of units) {
        if (Math.abs(seconds) >= duration) {
            return relativeDateFormatter.format(Math.trunc(seconds / duration), unit);
        }
    }
    return relativeDateFormatter.format(0, 'second');
}

function buildDateRenderer(kind) {
    if (!(kind === 'relative' || kind === 'calendar')) return () => '';
    return function(data, type) {
        if (!data) return '';
        const date = new Date(data);
        if (Number.isNaN(date.getTime())) return '';
        if (type === 'sort' || type === 'type') return date.getTime();
        const label = kind === 'relative'
            ? humanizeDate(date)
            : calendarDateFormatter.format(date);
        if (type !== 'display') return label;
        const element = document.createElement('time');
        element.className = 'small text-body-secondary';
        element.dateTime = data;
        element.title = tooltipDateFormatter.format(date);
        element.textContent = label;
        return element.outerHTML;
    };
}
