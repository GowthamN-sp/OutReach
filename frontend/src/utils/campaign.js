export function attachmentWarning(body, resumeId) {
  return (
    !resumeId &&
    /(?:attach(?:ed|ment)?[\s\S]{0,60}(?:resume|\bcv\b)|(?:resume|\bcv\b)[\s\S]{0,60}attach)/i.test(
      body,
    )
  );
}
