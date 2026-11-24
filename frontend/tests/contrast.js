() => {
  const rgb = (value) => value.match(/[\d.]+/g)?.map(Number);
  const luminance = (c) =>
    c
      .slice(0, 3)
      .map((v) => {
        const n = v / 255;
        return n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4;
      })
      .reduce((a, x, i) => a + x * [0.2126, 0.7152, 0.0722][i], 0);
  const failures = [];
  function check(el, label, pseudo) {
    const rect = el.getBoundingClientRect();
    if (
      !rect.width ||
      !rect.height ||
      rect.right <= 0 ||
      rect.left >= innerWidth
    )
      return;
    const style = getComputedStyle(el, pseudo);
    if (style.visibility === "hidden") return;
    let bg;
    for (let parent = el; parent; parent = parent.parentElement) {
      const color = rgb(getComputedStyle(parent).backgroundColor);
      if (color && (color.length === 3 || color[3] === 1)) {
        bg = color;
        break;
      }
    }
    if (!bg) return;
    const fg = rgb(el instanceof SVGElement ? style.fill : style.color);
    if (!fg) return;
    const values = [luminance(fg), luminance(bg)].sort((a, b) => b - a);
    const ratio = (values[0] + 0.05) / (values[1] + 0.05);
    const large =
      parseFloat(style.fontSize) >= 24 ||
      (parseFloat(style.fontSize) >= 18.67 &&
        parseInt(style.fontWeight) >= 700);
    if (ratio < (large ? 3 : 4.5) - 0.01)
      failures.push({
        text: label.slice(0, 40),
        class: el.className,
        ratio: +ratio.toFixed(2),
      });
  }
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode,
      el = node.parentElement;
    if (
      el &&
      node.textContent.trim() &&
      !el.closest("script,style,option,button:disabled,svg defs")
    )
      check(el, node.textContent.trim());
  }
  for (const el of document.querySelectorAll(
    "input:not(:disabled),textarea:not(:disabled),select:not(:disabled)",
  )) {
    if (["hidden", "file", "checkbox"].includes(el.type)) continue;
    check(el, el.getAttribute("name") || el.tagName);
    if (el.placeholder)
      check(el, "Placeholder: " + el.placeholder, "::placeholder");
  }
  return failures;
};
