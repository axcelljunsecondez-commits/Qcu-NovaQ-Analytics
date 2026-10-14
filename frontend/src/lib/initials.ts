// Up to two letters from the part of the email before @, for the account avatar.
export function initialsFor(email: string): string {
  const parts = email.split('@')[0].split(/[^a-zA-Z0-9]+/).filter(Boolean)
  const letters = parts.length >= 2 ? parts[0][0] + parts[1][0] : (parts[0] ?? '?').slice(0, 2)
  return letters.toUpperCase()
}
