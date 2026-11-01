/** Operating hours as a chip with a clock icon (spec 2026-10-29 §7.1, owner decision A6). The text is passed in unchanged. */
export function HoursChip({ text }: { text: string }) {
  return (
    <span className="hours-chip">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true" focusable="false">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </svg>
      <span>{text}</span>
    </span>
  )
}
