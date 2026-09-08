export function formatNumber(value: number | null | undefined, digits = 1): string {
  return (value ?? 0).toFixed(digits);
}

export function formatTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  return `${date.toLocaleDateString([], { month: "short", day: "numeric" })} ${date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}
