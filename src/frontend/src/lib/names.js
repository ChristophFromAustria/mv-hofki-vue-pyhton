/**
 * First guess at first/last name from what was typed into a person search:
 * "Maier, Anna" → Anna / Maier; "Anna Maier" → Anna / Maier; "Maier" → – / Maier.
 * The dialog lets the person swap or correct both.
 */
export function guessName(text) {
  const t = (text || "").trim().replace(/\s+/g, " ");
  if (!t) return { first_name: "", last_name: "" };
  if (t.includes(",")) {
    const [last, ...rest] = t.split(",");
    return { first_name: rest.join(",").trim(), last_name: last.trim() };
  }
  const words = t.split(" ");
  if (words.length === 1) return { first_name: "", last_name: t };
  return { first_name: words[0], last_name: words.slice(1).join(" ") };
}
