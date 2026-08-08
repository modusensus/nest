const PATHS = {
  home: 'M3 11 12 4l9 7M5 9.8V20h14V9.8',
  chat: 'M4 5.5h16v10.5H9.5L4 20z',
  folder: 'M3 6.5h6l2 2.5h10v9.5H3z',
  kanban: 'M4 4h4.5v16H4zM9.8 4h4.5v10H9.8zM15.5 4H20v13h-4.5z',
  check: 'M5 12.5l4.5 4.5L19 7',
  pen: 'M4.5 19.5l.9-3.8L16 5l3 3L8.4 18.6zM14.2 7l2.9 2.9',
  book: 'M6 3.5h12.5V20H7.5A1.5 1.5 0 0 0 6 21.5zM9 8h6',
  terminal: 'M3.5 5h17v14h-17zM7 9.5l3 3-3 3M12 15.5h5',
}

export default function Icon({ name, size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name] || ''} />
    </svg>
  )
}
