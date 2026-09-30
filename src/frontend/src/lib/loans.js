/** Loan state as shown in lists and badges. */

/** Today as YYYY-MM-DD in local time (loan dates are plain dates). */
export function todayIso(now = new Date()) {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Open and past its planned return day (as the backend's `overdue`). */
export function isOverdue(loan, today = todayIso()) {
  return !!loan && !loan.end_date && !!loan.due_date && loan.due_date < today;
}

/** { label, badge } for a loan: Zurückgegeben / Überfällig / Ausgeliehen. */
export function loanStatus(loan, today = todayIso()) {
  if (loan?.end_date) return { label: "Zurückgegeben", badge: "badge badge-gray" };
  if (isOverdue(loan, today)) return { label: "Überfällig", badge: "badge badge-warning" };
  return { label: "Ausgeliehen", badge: "badge badge-green" };
}
