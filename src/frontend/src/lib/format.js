/** Display formatting shared by detail pages (de-AT). */
export function formatDate(iso) {
  if (!iso) return "—";
  const [y, m, d] = String(iso).slice(0, 10).split("-");
  return d ? `${d}.${m}.${y}` : String(iso);
}

export function formatMoney(amount, abbreviation) {
  if (amount === null || amount === undefined || amount === "") return "—";
  const n = Number(amount).toLocaleString("de-AT", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return abbreviation ? `${n} ${abbreviation}` : n;
}
