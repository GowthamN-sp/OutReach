export const fmt = (n) => new Intl.NumberFormat("en-IN").format(n || 0);
export const date = (s) =>
  s
    ? new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : s + "Z").toLocaleDateString(
        "en-IN",
        { day: "2-digit", month: "short", year: "numeric" },
      )
    : "—";
export const time = (s) =>
  s
    ? new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : s + "Z").toLocaleString(
        "en-IN",
        { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" },
      )
    : "—";
