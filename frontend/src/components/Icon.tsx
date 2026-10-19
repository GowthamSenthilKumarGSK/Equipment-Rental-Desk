/**
 * One small icon set, drawn inline (24px grid, 2px stroke) so there is no icon dependency.
 * Icons are decoration: they are hidden from assistive technology, and every control that holds
 * one also carries visible text or an accessible name.
 */
const PATHS = {
  box: "M21 8 12 3 3 8v8l9 5 9-5V8ZM3.3 7.7 12 12.6l8.7-4.9M12 12.6V21",
  users:
    "M16 20v-1.5a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4V20M9.5 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM21 20v-1.5a4 4 0 0 0-3-3.9M15.5 4.2a3.5 3.5 0 0 1 0 6.6",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 7v5l3 2",
  chart: "M4 20V4M4 20h16M8 16v-4M12 16V8M16 16v-6M20 16v-9",
  menu: "M4 6h16M4 12h16M4 18h16",
  close: "M6 6l12 12M18 6 6 18",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14ZM20 20l-4-4",
  plus: "M12 5v14M5 12h14",
  check: "M5 12.5 10 17.5 19 7",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 11v5M12 8h.01",
  warning: "M12 4 2.5 20h19L12 4ZM12 10v4.5M12 17.5h.01",
  back: "M15 5 8 12l7 7",
  wrench:
    "M14.7 6.3a4 4 0 0 0 5 5L21 12.6 12.6 21 3 11.4l1.3-1.3a4 4 0 0 0 5-5L10.6 3.8 14.7 6.3ZM7 17h.01",
  rupee: "M7 5h10M7 9h10M7 5c5 0 7 1.5 7 4s-2 4-7 4l7 7",
  refresh: "M20 11a8 8 0 0 0-14.5-4M4 4v4h4M4 13a8 8 0 0 0 14.5 4M20 20v-4h-4",
  inbox: "M3 13h5l1.5 3h5L16 13h5M3 13l2.5-8h13L21 13v6H3v-6Z",
  calendar: "M4 7h16v13H4V7ZM4 11h16M8 3v4M16 3v4",
  funnel: "M3 5h18l-7 8v6l-4 2v-8L3 5Z",
  lock: "M6 11h12v9H6v-9ZM8.5 11V8a3.5 3.5 0 0 1 7 0v3",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4.5 20a7.5 7.5 0 0 1 15 0",
  wallet: "M3 7a2 2 0 0 1 2-2h13v4M3 7v11a2 2 0 0 0 2 2h15V9H5a2 2 0 0 1-2-2ZM16 14.5h.01",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
