export default function ResourceStatus({ resource, label }) {
  return (
    <>
      {resource.loading && (
        <p className="pad" role="status">
          {resource.data === undefined
            ? `Loading ${label}…`
            : `Refreshing ${label}…`}
        </p>
      )}
      {resource.error && (
        <div className="notice" role="alert">
          <span>
            Could not load {label}. {resource.error}
            {resource.data !== undefined &&
              " Showing the last successful result."}
          </span>
          <button className="text-link" onClick={resource.load}>
            Retry
          </button>
        </div>
      )}
    </>
  );
}
