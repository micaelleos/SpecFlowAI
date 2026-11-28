/** O losango do SpecFlow AI (decorativo: o nome aparece ao lado). */
export function Mark({ className = 'size-6' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={`${className} shrink-0`}>
      <rect x="4" y="4" width="16" height="16" rx="3" transform="rotate(45 12 12)" fill="#4f46e5" />
      <rect x="9" y="9" width="6" height="6" rx="1" transform="rotate(45 12 12)" fill="#fff" />
    </svg>
  )
}
